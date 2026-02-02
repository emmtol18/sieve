/**
 * Neural Sieve — Chrome Extension Background Service Worker
 *
 * Supports two modes:
 * - Local:  POST /api/capture/async on 127.0.0.1:8420 (no auth)
 * - Remote: POST /capture on relay server (Bearer token auth)
 *
 * Mode is determined by the configured API URL and key in chrome.storage.sync.
 */

const DEFAULT_CONFIG = {
  apiUrl: 'http://127.0.0.1:8420',
  apiKey: '',
};

async function getConfig() {
  return chrome.storage.sync.get(DEFAULT_CONFIG);
}

function isRemoteMode(config) {
  return !!(config.apiKey && !config.apiUrl.includes('127.0.0.1') && !config.apiUrl.includes('localhost'));
}

/**
 * Fire-and-forget capture to the configured endpoint.
 *
 * Local mode:  POST /api/capture/async (no auth)
 * Remote mode: POST /capture (Bearer token auth)
 */
async function captureAsync(content, sourceUrl, url = null, annotation = null) {
  const config = await getConfig();
  const remote = isRemoteMode(config);
  const baseUrl = config.apiUrl.replace(/\/+$/, '');
  const endpoint = remote ? '/capture' : '/api/capture/async';

  try {
    const payload = { content, source_url: sourceUrl };
    if (url) payload.url = url;
    if (annotation) payload.annotation = annotation;

    const headers = { 'Content-Type': 'application/json' };
    if (remote && config.apiKey) {
      headers['Authorization'] = `Bearer ${config.apiKey}`;
    }

    const res = await fetch(`${baseUrl}${endpoint}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      console.error(`[Neural Sieve] Capture failed: ${res.status}`);
      return false;
    }

    console.log(`[Neural Sieve] Capture queued (${remote ? 'remote' : 'local'})`);
    return true;
  } catch (e) {
    console.error('[Neural Sieve] Capture failed:', e.message);
    return false;
  }
}

// Create context menus on install
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'capture-selection',
    title: 'Save to Neural Sieve',
    contexts: ['selection']
  });

  chrome.contextMenus.create({
    id: 'add-to-collection',
    title: 'Add to Collection',
    contexts: ['selection']
  });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (!info.selectionText) return;

  if (info.menuItemId === 'capture-selection') {
    captureAsync(info.selectionText, tab.url);
  } else if (info.menuItemId === 'add-to-collection') {
    await addToCollection(tab.id, info.selectionText);
  }
});

/**
 * Add text to collection, injecting content script if needed
 */
async function addToCollection(tabId, text) {
  try {
    await chrome.tabs.sendMessage(tabId, { type: 'ADD_SELECTION', text });
    return;
  } catch (e) {
    // Content script not loaded yet
  }

  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ['content.js']
    });
    await chrome.scripting.insertCSS({
      target: { tabId },
      files: ['content.css']
    });

    await new Promise(r => setTimeout(r, 100));
    await chrome.tabs.sendMessage(tabId, { type: 'ADD_SELECTION', text });
  } catch (err) {
    console.error('[Neural Sieve] Cannot add to collection on this page');
  }
}

// Handle messages from popup and content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'CAPTURE') {
    captureAsync(message.content, message.source_url, message.url, message.annotation)
      .then(success => sendResponse({ success }))
      .catch(error => {
        console.error('[Neural Sieve] Message handler error:', error);
        sendResponse({ success: false });
      });
    return true;
  }

  if (message.type === 'GET_CONFIG') {
    getConfig().then(sendResponse);
    return true;
  }

  if (message.type === 'OPEN_POPUP') {
    console.log('[Neural Sieve] Badge clicked - user should click extension icon');
  }
});

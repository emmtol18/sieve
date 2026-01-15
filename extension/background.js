const API_URL = 'http://127.0.0.1:8420';

/**
 * Fire-and-forget capture to async endpoint.
 * Returns immediately after queueing - no waiting for LLM processing.
 */
async function captureAsync(content, sourceUrl, url = null, annotation = null) {
  try {
    const payload = {
      content,
      source_url: sourceUrl
    };

    // Include URL if provided (for URL capture)
    if (url) {
      payload.url = url;
    }

    // Include annotation if provided
    if (annotation) {
      payload.annotation = annotation;
    }

    const res = await fetch(`${API_URL}/api/capture/async`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      console.error(`[Neural Sieve] Capture failed: ${res.status}`);
      return false;
    }

    console.log('[Neural Sieve] Capture queued for background processing');
    return true;
  } catch (e) {
    console.error('[Neural Sieve] Capture failed:', e.message);
    return false;
  }
}

// Create context menus on install
chrome.runtime.onInstalled.addListener(() => {
  // Direct capture option
  chrome.contextMenus.create({
    id: 'capture-selection',
    title: 'Save to Neural Sieve',
    contexts: ['selection']
  });

  // Add to collection option
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
    // Direct capture (fire-and-forget)
    captureAsync(info.selectionText, tab.url);
  } else if (info.menuItemId === 'add-to-collection') {
    // Add to collection via content script
    try {
      await chrome.tabs.sendMessage(tab.id, {
        type: 'ADD_SELECTION',
        text: info.selectionText
      });
    } catch (e) {
      console.error('[Neural Sieve] Failed to add to collection:', e);
    }
  }
});

// Handle messages from popup and content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'CAPTURE') {
    captureAsync(message.content, message.source_url, message.url, message.annotation)
      .then(success => sendResponse({ success }))
      .catch(error => {
        console.error('[Neural Sieve] Message handler error:', error);
        sendResponse({ success: false });
      });
    return true; // Keep channel open for async response
  }

  if (message.type === 'OPEN_POPUP') {
    // Can't programmatically open popup, but could show a notification
    console.log('[Neural Sieve] Badge clicked - user should click extension icon');
  }
});

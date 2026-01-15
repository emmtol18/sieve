const API_URL = 'http://127.0.0.1:8420';

/**
 * Fire-and-forget capture to async endpoint.
 * Returns immediately after queueing - no waiting for LLM processing.
 */
async function captureAsync(content, sourceUrl, url = null) {
  try {
    const payload = {
      content,
      source_url: sourceUrl
    };

    // Include URL if provided (for URL capture)
    if (url) {
      payload.url = url;
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

// Create context menu on install
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'capture-selection',
    title: 'Save to Neural Sieve',
    contexts: ['selection']
  });
});

// Handle context menu clicks (fire-and-forget)
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== 'capture-selection' || !info.selectionText) return;
  captureAsync(info.selectionText, tab.url);
});

// Handle messages from popup (fire-and-forget capture)
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'CAPTURE') {
    captureAsync(message.content, message.source_url, message.url)
      .then(success => sendResponse({ success }))
      .catch(error => {
        console.error('[Neural Sieve] Message handler error:', error);
        sendResponse({ success: false });
      });
    return true; // Keep channel open for async response
  }
});

const API_URL = 'http://127.0.0.1:8420';

// Create context menu on install
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'capture-selection',
    title: 'Save to Neural Sieve',
    contexts: ['selection']
  });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== 'capture-selection' || !info.selectionText) return;

  try {
    const res = await fetch(`${API_URL}/api/capture`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content: info.selectionText,
        source_url: tab.url
      })
    });

    if (!res.ok) throw new Error('Server error');

    const data = await res.json();

    // Show notification (optional - requires notifications permission)
    console.log(`Captured: ${data.title}`);
  } catch (e) {
    console.error('Capture failed:', e);
  }
});

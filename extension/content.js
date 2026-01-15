/**
 * Neural Sieve Content Script
 * Manages multi-selection collection with floating badge UI
 */

(function() {
  'use strict';

  const STORAGE_KEY = 'neural_sieve_collections';
  const MAX_COLLECTION_SIZE = 50;  // Max items per collection
  let badge = null;
  let toast = null;
  let saveLock = false;  // Simple mutex for race condition prevention

  /**
   * Get storage key for current URL (normalized)
   */
  function getUrlKey() {
    const url = new URL(window.location.href);
    url.hash = '';
    url.search = '';
    return url.href;
  }

  /**
   * Load collection for current page
   */
  async function loadCollection() {
    try {
      const result = await chrome.storage.local.get(STORAGE_KEY);
      const collections = result[STORAGE_KEY] || {};
      return collections[getUrlKey()] || [];
    } catch (e) {
      console.error('[Neural Sieve] Failed to load collection:', e);
      return [];
    }
  }

  /**
   * Save collection for current page
   */
  async function saveCollection(selections) {
    try {
      const result = await chrome.storage.local.get(STORAGE_KEY);
      const collections = result[STORAGE_KEY] || {};

      if (selections.length === 0) {
        delete collections[getUrlKey()];
      } else {
        collections[getUrlKey()] = selections;
      }

      await chrome.storage.local.set({ [STORAGE_KEY]: collections });
    } catch (e) {
      console.error('[Neural Sieve] Failed to save collection:', e);
    }
  }

  /**
   * Add selection to collection (with mutex to prevent race conditions)
   */
  async function addSelection(text) {
    if (!text || !text.trim()) return;

    // Wait for any pending save to complete
    while (saveLock) {
      await new Promise(resolve => setTimeout(resolve, 50));
    }

    saveLock = true;
    try {
      const selections = await loadCollection();
      const trimmed = text.trim();

      // Avoid duplicates
      if (selections.some(s => s.text === trimmed)) {
        showToast('Already collected');
        return;
      }

      // Check collection size limit
      if (selections.length >= MAX_COLLECTION_SIZE) {
        showToast('Collection full (max 50)');
        return;
      }

      selections.push({
        text: trimmed,
        timestamp: Date.now()
      });

      await saveCollection(selections);
      updateBadge(selections.length);
      showToast('Added to collection');
    } finally {
      saveLock = false;
    }
  }

  /**
   * Clear collection for current page
   */
  async function clearCollection() {
    await saveCollection([]);
    updateBadge(0);
    showToast('Collection cleared');
  }

  /**
   * Create SVG close icon
   */
  function createCloseIcon() {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('viewBox', '0 0 24 24');

    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('stroke-linecap', 'round');
    path.setAttribute('stroke-linejoin', 'round');
    path.setAttribute('stroke-width', '2');
    path.setAttribute('d', 'M6 18L18 6M6 6l12 12');

    svg.appendChild(path);
    return svg;
  }

  /**
   * Create badge element using safe DOM methods
   */
  function createBadge() {
    if (badge) return badge;

    badge = document.createElement('div');
    badge.className = 'neural-sieve-badge';

    const countSpan = document.createElement('span');
    countSpan.className = 'neural-sieve-badge-count';
    countSpan.textContent = '0';

    const textSpan = document.createElement('span');
    textSpan.className = 'neural-sieve-badge-text';
    textSpan.textContent = 'selections';

    const clearBtn = document.createElement('button');
    clearBtn.className = 'neural-sieve-badge-clear';
    clearBtn.title = 'Clear collection';
    clearBtn.appendChild(createCloseIcon());

    badge.appendChild(countSpan);
    badge.appendChild(textSpan);
    badge.appendChild(clearBtn);

    // Click badge to open popup (extension action)
    badge.addEventListener('click', (e) => {
      if (e.target.closest('.neural-sieve-badge-clear')) return;
      chrome.runtime.sendMessage({ type: 'OPEN_POPUP' });
    });

    // Clear button
    clearBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      clearCollection();
    });

    document.body.appendChild(badge);
    return badge;
  }

  /**
   * Create toast element
   */
  function createToast() {
    if (toast) return toast;

    toast = document.createElement('div');
    toast.className = 'neural-sieve-toast';
    document.body.appendChild(toast);
    return toast;
  }

  /**
   * Update badge count (handles SPA DOM changes)
   */
  function updateBadge(count) {
    // Check if badge is still attached to DOM (handles SPA navigation)
    if (!badge || !badge.isConnected) {
      badge = null;
      createBadge();
    }

    const countEl = badge.querySelector('.neural-sieve-badge-count');
    const textEl = badge.querySelector('.neural-sieve-badge-text');

    countEl.textContent = count;
    textEl.textContent = count === 1 ? 'selection' : 'selections';

    if (count > 0) {
      badge.classList.add('visible');
    } else {
      badge.classList.remove('visible');
    }
  }

  /**
   * Show toast message (handles SPA DOM changes)
   */
  function showToast(message) {
    // Check if toast is still attached to DOM
    if (!toast || !toast.isConnected) {
      toast = null;
      createToast();
    }

    toast.textContent = message;
    toast.classList.add('visible');

    setTimeout(() => {
      if (toast && toast.isConnected) {
        toast.classList.remove('visible');
      }
    }, 2000);
  }

  /**
   * Initialize content script
   */
  async function init() {
    createBadge();
    createToast();

    // Load existing collection
    const selections = await loadCollection();
    updateBadge(selections.length);
  }

  /**
   * Listen for messages from background/popup
   */
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'ADD_SELECTION') {
      addSelection(message.text).then(() => sendResponse({ success: true }));
      return true;
    }

    if (message.type === 'GET_COLLECTION') {
      loadCollection().then(selections => {
        sendResponse({ selections, url: window.location.href });
      });
      return true;
    }

    if (message.type === 'CLEAR_COLLECTION') {
      clearCollection().then(() => sendResponse({ success: true }));
      return true;
    }
  });

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

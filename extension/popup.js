const API_URL = 'http://127.0.0.1:8420';

let selectedText = '';
let pageUrl = '';

async function checkServer() {
  const status = document.getElementById('status');
  try {
    const res = await fetch(`${API_URL}/api/health`);
    if (res.ok) {
      status.classList.remove('offline');
      return true;
    }
  } catch (e) {}
  status.classList.add('offline');
  return false;
}

async function getSelection() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    pageUrl = tab.url;

    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => window.getSelection().toString().trim()
    });

    return results?.[0]?.result || '';
  } catch (e) {
    console.error('Selection error:', e);
    return '';
  }
}

async function getPageContent() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const selectors = ['article', 'main', '[role="main"]', '.content', '#content'];

        for (const sel of selectors) {
          const el = document.querySelector(sel);
          if (el?.innerText.trim().length > 100) {
            return el.innerText.trim();
          }
        }

        const body = document.body.cloneNode(true);
        body.querySelectorAll('script, style, nav, header, footer, aside').forEach(el => el.remove());
        return body.innerText.trim();
      }
    });

    return results?.[0]?.result || '';
  } catch (e) {
    console.error('Page content error:', e);
    return '';
  }
}

/**
 * Fire-and-forget capture via background service worker.
 * Sends message to background, shows instant feedback, closes popup immediately.
 */
async function capture(content, url = null) {
  const btn = document.getElementById('capture-btn');
  const pageBtn = document.getElementById('page-btn');
  const urlBtn = document.getElementById('url-btn');
  const msg = document.getElementById('message');

  // Disable all buttons immediately
  btn.disabled = true;
  pageBtn.disabled = true;
  urlBtn.disabled = true;
  btn.textContent = 'Queued...';

  // Send to background service worker (fire-and-forget)
  chrome.runtime.sendMessage({
    type: 'CAPTURE',
    content: content,
    url: url,
    source_url: pageUrl
  });

  // Show instant success and close quickly
  msg.className = 'message success';
  msg.textContent = 'Queued for capture';

  // Close popup after brief feedback (300ms)
  setTimeout(() => window.close(), 300);
}

function isValidUrl(string) {
  try {
    const url = new URL(string);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch (_) {
    return false;
  }
}

async function captureUrl() {
  const urlInput = document.getElementById('url-input');
  const url = urlInput.value.trim();
  const msg = document.getElementById('message');

  if (!url) {
    msg.className = 'message error';
    msg.textContent = 'Please enter a URL';
    return;
  }

  if (!isValidUrl(url)) {
    msg.className = 'message error';
    msg.textContent = 'Please enter a valid URL';
    return;
  }

  capture('', url);
}

async function init() {
  const serverUp = await checkServer();

  selectedText = await getSelection();

  const preview = document.getElementById('preview');
  const captureBtn = document.getElementById('capture-btn');
  const pageBtn = document.getElementById('page-btn');
  const urlInput = document.getElementById('url-input');
  const urlBtn = document.getElementById('url-btn');

  if (selectedText) {
    preview.textContent = selectedText.substring(0, 200) + (selectedText.length > 200 ? '...' : '');
    preview.classList.remove('empty');
    captureBtn.disabled = !serverUp;
  } else {
    preview.textContent = 'Select text on the page, or capture the full page';
    preview.classList.add('empty');
  }

  // Enable/disable buttons based on server status
  pageBtn.disabled = !serverUp;
  urlBtn.disabled = !serverUp;
  urlInput.disabled = !serverUp;

  captureBtn.addEventListener('click', () => {
    if (selectedText) capture(selectedText);
  });

  pageBtn.addEventListener('click', async () => {
    const content = await getPageContent();
    if (content) {
      capture(content);
    } else {
      const msg = document.getElementById('message');
      msg.className = 'message error';
      msg.textContent = 'Could not extract page content';
    }
  });

  urlBtn.addEventListener('click', captureUrl);

  // Allow Enter key to submit URL
  urlInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') captureUrl();
  });
}

init();

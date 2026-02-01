let selectedText = '';
let pageUrl = '';
let collectionItems = [];

async function getConfig() {
  return new Promise(resolve => {
    chrome.runtime.sendMessage({ type: 'GET_CONFIG' }, resolve);
  });
}

function isRemoteMode(config) {
  return !!(config.apiKey && !config.apiUrl.includes('127.0.0.1') && !config.apiUrl.includes('localhost'));
}

async function checkServer() {
  const status = document.getElementById('status');
  const config = await getConfig();
  const remote = isRemoteMode(config);
  const baseUrl = config.apiUrl.replace(/\/+$/, '');
  const healthUrl = remote ? `${baseUrl}/health` : `${baseUrl}/api/health`;

  // Show mode label
  const modeLabel = document.getElementById('mode-label');
  if (modeLabel) {
    modeLabel.textContent = remote ? 'Remote' : 'Local';
    modeLabel.className = `mode-label ${remote ? 'mode-remote' : 'mode-local'}`;
  }

  try {
    const res = await fetch(healthUrl);
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
 */
async function capture(content, url = null) {
  const btn = document.getElementById('capture-btn');
  const pageBtn = document.getElementById('page-btn');
  const urlBtn = document.getElementById('url-btn');
  const msg = document.getElementById('message');

  btn.disabled = true;
  pageBtn.disabled = true;
  urlBtn.disabled = true;
  btn.textContent = 'Queued...';

  chrome.runtime.sendMessage({
    type: 'CAPTURE',
    content: content,
    url: url,
    source_url: pageUrl
  });

  msg.className = 'message success';
  msg.textContent = 'Queued for capture';

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

function isRestrictedUrl(url) {
  if (!url) return true;
  return url.startsWith('chrome://') ||
         url.startsWith('chrome-extension://') ||
         url.startsWith('about:') ||
         url.startsWith('edge://') ||
         url.startsWith('brave://');
}

async function loadCollection() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (isRestrictedUrl(tab.url)) {
      return { selections: [], restricted: true };
    }

    const response = await chrome.tabs.sendMessage(tab.id, { type: 'GET_COLLECTION' });
    return { selections: response?.selections || [], restricted: false };
  } catch (e) {
    return { selections: [], restricted: true };
  }
}

function updateCollectionUI() {
  const section = document.getElementById('collection-section');
  const countEl = document.getElementById('collection-count');
  const itemsEl = document.getElementById('collection-items');

  if (collectionItems.length === 0) {
    section.classList.remove('has-items');
    return;
  }

  section.classList.add('has-items');
  countEl.textContent = collectionItems.length;

  itemsEl.replaceChildren();

  collectionItems.forEach(item => {
    const div = document.createElement('div');
    div.className = 'collection-item';

    const textSpan = document.createElement('span');
    textSpan.className = 'collection-item-text';
    textSpan.textContent = item.text.substring(0, 150) + (item.text.length > 150 ? '...' : '');

    div.appendChild(textSpan);
    itemsEl.appendChild(div);
  });
}

async function clearCollection() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    await chrome.tabs.sendMessage(tab.id, { type: 'CLEAR_COLLECTION' });
    collectionItems = [];
    updateCollectionUI();
  } catch (e) {
    console.error('Failed to clear collection:', e);
  }
}

const MAX_ANNOTATION_LENGTH = 1000;

async function captureCollection() {
  if (collectionItems.length === 0) return;

  const annotation = document.getElementById('annotation-input').value.trim().substring(0, MAX_ANNOTATION_LENGTH);
  const content = collectionItems.map(item => item.text).join('\n\n---\n\n');

  const btn = document.getElementById('collection-capture-btn');
  btn.disabled = true;
  btn.textContent = 'Queued...';

  chrome.runtime.sendMessage({
    type: 'CAPTURE',
    content: content,
    source_url: pageUrl,
    annotation: annotation || null
  });

  await clearCollection();

  const msg = document.getElementById('message');
  msg.className = 'message success';
  msg.textContent = 'Collection captured';

  setTimeout(() => window.close(), 300);
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
  const collectionClearBtn = document.getElementById('collection-clear');
  const collectionCaptureBtn = document.getElementById('collection-capture-btn');
  const annotationInput = document.getElementById('annotation-input');

  const { selections, restricted } = await loadCollection();
  collectionItems = selections;

  if (restricted) {
    const collectionSection = document.getElementById('collection-section');
    collectionSection.classList.remove('has-items');
  }

  updateCollectionUI();

  if (selectedText) {
    preview.textContent = selectedText.substring(0, 200) + (selectedText.length > 200 ? '...' : '');
    preview.classList.remove('empty');
    captureBtn.disabled = !serverUp;
  } else {
    preview.textContent = 'Select text on the page, or capture the full page';
    preview.classList.add('empty');
  }

  pageBtn.disabled = !serverUp;
  urlBtn.disabled = !serverUp;
  urlInput.disabled = !serverUp;
  collectionCaptureBtn.disabled = !serverUp || collectionItems.length === 0;

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

  urlInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') captureUrl();
  });

  collectionClearBtn.addEventListener('click', clearCollection);
  collectionCaptureBtn.addEventListener('click', captureCollection);
}

init();

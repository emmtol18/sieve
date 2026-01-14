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

function resetCaptureButton(btn) {
  btn.textContent = '';
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'icon');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('viewBox', '0 0 24 24');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('stroke-linecap', 'round');
  path.setAttribute('stroke-linejoin', 'round');
  path.setAttribute('stroke-width', '2');
  path.setAttribute('d', 'M12 6v6m0 0v6m0-6h6m-6 0H6');
  svg.appendChild(path);
  btn.appendChild(svg);
  btn.appendChild(document.createTextNode(' Capture Selection'));
}

async function capture(content) {
  const btn = document.getElementById('capture-btn');
  const msg = document.getElementById('message');

  btn.disabled = true;
  btn.textContent = 'Capturing...';

  try {
    const res = await fetch(`${API_URL}/api/capture`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content,
        source_url: pageUrl
      })
    });

    if (!res.ok) throw new Error('Server error');

    const data = await res.json();
    msg.className = 'message success';
    msg.textContent = 'Captured: ' + data.title;

    setTimeout(() => window.close(), 1200);
  } catch (e) {
    msg.className = 'message error';
    msg.textContent = 'Error: ' + e.message;
  } finally {
    btn.disabled = false;
    resetCaptureButton(btn);
  }
}

async function init() {
  await checkServer();

  selectedText = await getSelection();

  const preview = document.getElementById('preview');
  const captureBtn = document.getElementById('capture-btn');

  if (selectedText) {
    preview.textContent = selectedText.substring(0, 200) + (selectedText.length > 200 ? '...' : '');
    preview.classList.remove('empty');
    captureBtn.disabled = false;
  } else {
    preview.textContent = 'Select text on the page, or capture the full page';
    preview.classList.add('empty');
  }

  captureBtn.addEventListener('click', () => {
    if (selectedText) capture(selectedText);
  });

  document.getElementById('page-btn').addEventListener('click', async () => {
    const content = await getPageContent();
    if (content) {
      capture(content);
    } else {
      const msg = document.getElementById('message');
      msg.className = 'message error';
      msg.textContent = 'Could not extract page content';
    }
  });
}

init();

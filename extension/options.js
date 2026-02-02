/**
 * Neural Sieve — Options Page Script
 */

const apiUrlInput = document.getElementById('apiUrl');
const apiKeyInput = document.getElementById('apiKey');
const saveBtn = document.getElementById('save');
const testBtn = document.getElementById('test');
const statusEl = document.getElementById('status');

// Load saved settings
chrome.storage.sync.get(
  { apiUrl: 'http://127.0.0.1:8420', apiKey: '' },
  (items) => {
    apiUrlInput.value = items.apiUrl;
    apiKeyInput.value = items.apiKey;
  }
);

function setStatus(text, type) {
  statusEl.textContent = text;
  statusEl.className = 'status ' + (type || '');
}

// Save settings
saveBtn.addEventListener('click', () => {
  const apiUrl = apiUrlInput.value.trim().replace(/\/+$/, '');
  const apiKey = apiKeyInput.value.trim();

  if (!apiUrl) {
    setStatus('API URL is required', 'error');
    return;
  }

  chrome.storage.sync.set({ apiUrl, apiKey }, () => {
    setStatus('Settings saved', 'success');
  });
});

// Test connection
testBtn.addEventListener('click', async () => {
  const apiUrl = apiUrlInput.value.trim().replace(/\/+$/, '');
  const apiKey = apiKeyInput.value.trim();

  if (!apiUrl) {
    setStatus('Enter an API URL first', 'error');
    return;
  }

  setStatus('Testing...');

  const isRemote = apiKey && !apiUrl.includes('127.0.0.1') && !apiUrl.includes('localhost');
  const healthUrl = apiUrl + (isRemote ? '/health' : '/api/health');

  try {
    const response = await fetch(healthUrl, { method: 'GET' });
    if (response.ok) {
      const data = await response.json();
      const label = data.service || data.version || 'ok';
      setStatus(`Connected (${label})`, 'success');
    } else {
      setStatus(`HTTP ${response.status}`, 'error');
    }
  } catch (err) {
    setStatus(`Connection failed: ${err.message}`, 'error');
  }
});

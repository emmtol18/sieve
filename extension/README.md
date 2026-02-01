# Neural Sieve Chrome Extension

## Installation

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (top right)
3. Click "Load unpacked" and select this `extension/` folder

## Usage

**Local mode** (default — no setup needed beyond installation):

1. Start Neural Sieve: `sieve start`
2. Select text on any webpage and click the extension icon
3. Or right-click selected text and choose "Save to Neural Sieve"

**Remote mode** (capture from anywhere via relay server):

1. Deploy the relay server (see `relay/DEPLOYMENT.md`)
2. Right-click the extension icon > Options
3. Set **API URL** to your tunnel URL (e.g. `https://sieve.yourdomain.com`)
4. Set **API Key** to your relay key (`sieve_live_...`)
5. Click "Test Connection" to verify

## Status Indicator

- **Green dot**: Server is reachable
- **Red dot**: Server is offline
- **Local** / **Remote** label: shows which mode is active

## How It Works

| Mode | Endpoint | Auth |
|------|----------|------|
| Local | `POST /api/capture/async` on `127.0.0.1:8420` | None (same-machine) |
| Remote | `POST /capture` on your relay URL | Bearer token |

The extension auto-detects mode based on whether an API key is configured and the URL is non-localhost.

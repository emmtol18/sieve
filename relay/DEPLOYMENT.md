# Sieve Relay — Deployment Guide

## Architecture

```
Phone/Chrome Extension
        |
        | HTTPS (Cloudflare Tunnel) + Bearer API key
        v
+-------------------------+
|  VPS: sieve-relay       |  <-- Dumb queue, no secrets except hashed API keys
|  POST /capture          |
|  GET  /captures/pending |
|  POST /captures/{id}/ack|
|  SQLite storage         |
+----------+--------------+
           | local `sieve pull` fetches pending
           v
+-------------------------+
|  Local machine          |
|  Processor (OpenAI)     |
|  Vault (markdown files) |
|  MCP server (Claude)    |
+-------------------------+
```

**Security properties:** If VPS is compromised, attacker can only read pending raw captures (URLs/text) and insert fake captures. They cannot access the vault, MCP data, or OpenAI key.

---

## VPS Setup

### 1. Harden VPS

```bash
# Disable password SSH (edit /etc/ssh/sshd_config)
PasswordAuthentication no
PermitRootLogin no

# Firewall: SSH only (Cloudflare Tunnel handles HTTPS)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw enable

# Auto-updates
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 2. Create sieve user

```bash
sudo useradd -r -m -s /bin/bash sieve
sudo su - sieve
```

### 3. Install dependencies

```bash
# Install uv (as sieve user)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Clone repo and install
git clone https://github.com/your-org/neural-sieve.git
cd neural-sieve/relay
uv venv && uv pip install -e ".[dev]"
```

### 4. Initialize database and keys

```bash
cd ~/neural-sieve/relay

# Create database
uv run relay init-db

# Generate keys
uv run relay generate-key --name "chrome-extension"
uv run relay generate-key --name "ios-shortcut"
uv run relay generate-key --name "admin" --admin

# Save keys somewhere safe - they cannot be retrieved later!
```

### 5. Install Cloudflare Tunnel

```bash
# Install cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

# Login (as sieve user)
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create sieve-relay

# Configure tunnel
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: sieve-relay
credentials-file: /home/sieve/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: sieve.yourdomain.com
    service: http://localhost:8421
  - service: http_status:404
EOF

# Route DNS (creates CNAME record)
cloudflared tunnel route dns sieve-relay sieve.yourdomain.com
```

### 6. Systemd services

Create `/etc/systemd/system/sieve-relay.service`:

```ini
[Unit]
Description=Sieve Relay Server
After=network.target

[Service]
Type=simple
User=sieve
WorkingDirectory=/home/sieve/neural-sieve/relay
ExecStart=/home/sieve/.local/bin/uv run relay serve
Restart=always
RestartSec=5
Environment=RELAY_DB_PATH=/home/sieve/data/relay.db

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/cloudflared.service`:

```ini
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=simple
User=sieve
ExecStart=/usr/local/bin/cloudflared tunnel run sieve-relay
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable sieve-relay cloudflared
sudo systemctl start sieve-relay cloudflared
```

### 7. Verify

```bash
# Local test
curl http://localhost:8421/health

# Remote test (through tunnel)
curl https://sieve.yourdomain.com/health

# Test capture
curl -X POST https://sieve.yourdomain.com/capture \
  -H "Authorization: Bearer sieve_live_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

---

## Local Machine Setup

Add to your `.env` file:

```bash
# Remote relay (optional)
SIEVE_RELAY_URL=https://sieve.yourdomain.com
SIEVE_RELAY_ADMIN_KEY=sieve_live_your_admin_key_here
SIEVE_RELAY_PULL_INTERVAL=60
```

The pull loop starts automatically with `sieve start` when these are configured. For manual one-shot pulls:

```bash
sieve pull --once
```

---

## iOS Shortcut Setup

Create a new Shortcut in the iOS Shortcuts app:

1. **Name:** "Save to Sieve"
2. **Accept Share Sheet input:** URLs, Text, Safari Web Pages
3. **Get URLs from Input** (action) — extracts URL from share sheet
4. **Get Contents of URL** (action):
   - URL: `https://sieve.yourdomain.com/capture`
   - Method: POST
   - Headers:
     - `Authorization`: `Bearer sieve_live_your_ios_key_here`
     - `Content-Type`: `application/json`
   - Body (JSON):
     ```json
     {"url": "<URLs from step 3>"}
     ```
5. **If** result contains "id":
   - **Show Notification:** "Saved to Sieve"
6. **Otherwise:**
   - **Show Notification:** "Failed to save"

### For text captures:

Add a parallel path that checks input type:

- If input is Text (not URL):
  - Body: `{"content": "<Shortcut Input>"}`

---

## Chrome Extension Setup

1. Open `chrome://extensions`
2. Enable "Developer mode"
3. Click "Load unpacked" and select the `extension/` directory
4. Click the extension icon > right-click > Options
5. Set:
   - **API URL:** `https://sieve.yourdomain.com` (for remote) or `http://127.0.0.1:8420` (for local)
   - **API Key:** your Chrome extension key (for remote only)
6. Click "Test Connection" to verify

---

## Key Management

```bash
# List all keys
uv run relay list-keys

# Generate a new key
uv run relay generate-key --name "new-device"

# Revoke a compromised key
uv run relay revoke-key sieve_live_abc12345
```

---

## Monitoring

```bash
# Check service status
sudo systemctl status sieve-relay
sudo systemctl status cloudflared

# View logs
sudo journalctl -u sieve-relay -f
sudo journalctl -u cloudflared -f
```

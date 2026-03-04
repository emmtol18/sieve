# Deployment Guide — Fly.io

Deploy Neural Sieve v3 to Fly.io with PostgreSQL.

## Prerequisites

1. [Fly.io account](https://fly.io/app/sign-up) (free tier available)
2. [flyctl CLI](https://fly.io/docs/flyctl/install/)
3. OpenAI API key

## Step 1: Install Fly CLI

```bash
# macOS
brew install flyctl

# Or curl
curl -L https://fly.io/install.sh | sh
```

Log in:

```bash
fly auth login
```

## Step 2: Create the Dockerfile

Create `Dockerfile` in the project root:

```dockerfile
FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ src/
COPY alembic.ini ./

# Expose port
EXPOSE 8421

# Run migrations then start server
CMD ["sh", "-c", "uv run alembic upgrade head && uv run sieve serve --port 8421"]
```

## Step 3: Create fly.toml

Create `fly.toml` in the project root:

```toml
app = "neural-sieve"
primary_region = "iad"

[build]

[http_service]
  internal_port = 8421
  force_https = true
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 0

[env]
  SIEVE_HOST = "0.0.0.0"
  SIEVE_PORT = "8421"
```

## Step 4: Launch the App

```bash
cd /path/to/neural-sieve-v3

# Create the app (choose a unique name)
fly launch --no-deploy

# When prompted:
#   - App name: neural-sieve (or your preferred name)
#   - Region: choose closest to you
#   - PostgreSQL: YES (choose "Development" for free tier)
#   - Redis: No
```

This creates the app and a PostgreSQL database. Fly automatically sets the `DATABASE_URL` secret.

## Step 5: Set Secrets

```bash
# Generate a strong JWT secret
fly secrets set SIEVE_JWT_SECRET=$(openssl rand -hex 32)

# Set your BlackFuel API key
fly secrets set SIEVE_FUEL_API_KEY=sk-your-key-here

# Set custom LLM API base (default: https://api.fuel1.ai/v1)
fly secrets set SIEVE_FUEL_API_BASE=https://api.fuel1.ai/v1

# Google OAuth (optional — sign-in with Google)
# Create credentials at https://console.cloud.google.com/apis/credentials
fly secrets set SIEVE_GOOGLE_CLIENT_ID=your-google-client-id
fly secrets set SIEVE_GOOGLE_CLIENT_SECRET=your-google-client-secret
fly secrets set SIEVE_GOOGLE_REDIRECT_URI=https://neural-sieve.fly.dev/auth/google/callback

# CORS — allow your domain and the browser extension
fly secrets set SIEVE_CORS_ORIGINS="https://neural-sieve.fly.dev,https://app.neuralsieve.com"

# The DATABASE_URL is set automatically by Fly PostgreSQL
# But our app expects SIEVE_DATABASE_URL, so set it:
fly secrets set SIEVE_DATABASE_URL=$(fly postgres config show --app neural-sieve-db | grep DATABASE_URL | awk '{print $2}')
```

**If the automatic DATABASE_URL doesn't work**, get it manually:

```bash
# List your Fly Postgres apps
fly postgres list

# Get the connection string
fly postgres connect -a <your-postgres-app-name>

# Then set it
fly secrets set SIEVE_DATABASE_URL="postgresql+asyncpg://user:password@host:5432/neural_sieve_v3"
```

**Important:** The database URL from Fly uses `postgres://` prefix. You need to change it to `postgresql+asyncpg://` for SQLAlchemy async.

## Step 6: Deploy

```bash
fly deploy
```

Watch the deployment:

```bash
fly logs
```

Verify it's running:

```bash
fly status

# Open in browser
fly open
```

Your app is now live at `https://neural-sieve.fly.dev` (or your chosen name).

## Step 7: Create Your Account

```bash
# Replace with your actual app URL
curl -X POST https://neural-sieve.fly.dev/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "you@example.com",
    "password": "your-secure-password",
    "display_name": "Your Name"
  }'
```

Save the `api_key` from the response. You'll need it for the MCP server and CLI.

## Step 8: Connect Claude Code

Add this to your Claude Code configuration:

**Option A: Global MCP config** (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "neural-sieve": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/neural-sieve-v3", "sieve", "mcp"],
      "env": {
        "SIEVE_API_URL": "https://neural-sieve.fly.dev",
        "SIEVE_API_KEY": "your-api-key-from-step-7"
      }
    }
  }
}
```

**Option B: Per-project** (`.mcp.json` in your project):

```json
{
  "mcpServers": {
    "neural-sieve": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/neural-sieve-v3", "sieve", "mcp"],
      "env": {
        "SIEVE_API_URL": "https://neural-sieve.fly.dev",
        "SIEVE_API_KEY": "your-api-key-from-step-7"
      }
    }
  }
}
```

Restart Claude Code. You should see "neural-sieve" in your MCP connections.

## Step 9: Set Up Skills Compilation

```bash
# Set env vars for the CLI
export SIEVE_API_URL=https://neural-sieve.fly.dev
export SIEVE_API_KEY=your-api-key

# Compile all capsules into Claude Code skills (one per capsule)
uv run sieve compile --all --output ~/.claude/skills

# Or group by author/category/pack
uv run sieve compile --by author --all --output ~/.claude/skills

# Or compile into a specific project
uv run sieve compile --all --output /path/to/project/.claude/skills
```

Skills are regenerated each time you run `compile`. Run it after capturing new knowledge.

## Step 10: Configure Sieve Clipper Extension

The Sieve Clipper browser extension captures web content directly into Neural Sieve.

### Production default

The extension defaults to `https://app.neuralsieve.com`. If your Fly app uses a **custom domain**, users need to update the server URL either:

- **In the popup** — when not connected, a "Server URL" field appears above the API key input
- **In extension settings** — Account → Server URL

### For self-hosted / dev

If running locally or on a different host, set the server URL to your instance (e.g. `http://localhost:8421`).

### Connecting

1. Install the Sieve Clipper extension
2. Click the extension icon — the popup shows the login form
3. Set the server URL if not using the default
4. Paste your API key (from dashboard Settings page)
5. Click **Connect**

The extension verifies the key against your server and displays the clipper UI on success.

## User Setup Guide (Non-Technical)

### For users who just want to use Neural Sieve:

1. **Sign up** at `https://your-app.fly.dev/login`
2. **Install Sieve Clipper** — the browser extension for capturing web content
3. **Connect the extension** — paste your API key from the Settings page
4. **Capture knowledge** — use the extension on any page, or the Capture page to paste a URL
5. **Browse your sieve** on the My Sieve page
6. **Discover packs** — subscribe to curated creator packs on the Discover page
7. **Access from phone** — the dashboard works on mobile browsers. Add to home screen for app-like experience.

### For users who also use Claude Code:

1. Follow Steps 8-9 above to connect MCP + compile skills
2. Claude will automatically search your knowledge during coding sessions
3. Run `sieve compile` periodically to update your skills

## Monitoring

```bash
# View logs
fly logs

# Check app status
fly status

# Scale up if needed
fly scale count 2

# SSH into the machine
fly ssh console
```

## Updating

```bash
# Pull latest code
git pull

# Deploy
fly deploy
```

## Database Management

```bash
# Connect to Postgres directly
fly postgres connect -a <your-postgres-app-name>

# Run migrations manually
fly ssh console -C "uv run alembic upgrade head"

# Backup
fly postgres backup create -a <your-postgres-app-name>
```

## Costs (Fly.io)

| Resource | Free Tier | Paid |
|----------|-----------|------|
| App machines | 3 shared-cpu-1x (256MB) | $1.94/mo per machine |
| PostgreSQL | 1 shared-cpu-1x (256MB) | $1.94/mo |
| Bandwidth | 100GB/mo | $0.02/GB after |
| Storage | 3GB | $0.15/GB/mo |

The free tier is enough for personal use. For a team, expect ~$5-10/mo.

## Troubleshooting

**App won't start:**
```bash
fly logs  # Check for errors
fly secrets list  # Verify all secrets are set
```

**Database connection fails:**
- Ensure `SIEVE_DATABASE_URL` uses `postgresql+asyncpg://` prefix (not `postgres://`)
- Check the Postgres app is running: `fly status -a <postgres-app-name>`

**MCP server can't connect:**
- Verify `SIEVE_API_URL` points to your Fly app (with `https://`)
- Verify `SIEVE_API_KEY` matches the key from signup
- Check the app is running: `curl https://your-app.fly.dev/api/auth/me -H "Authorization: Bearer your-key"`

**Extension gets CORS errors:**
- Ensure `SIEVE_CORS_ORIGINS` includes your app domain: `fly secrets set SIEVE_CORS_ORIGINS="https://your-app.fly.dev"`
- Multiple origins: separate with commas (no spaces)

**Migrations fail:**
```bash
fly ssh console -C "uv run alembic current"   # Check current state
fly ssh console -C "uv run alembic upgrade head"  # Run pending
```

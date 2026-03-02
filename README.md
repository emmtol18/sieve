# Neural Sieve v3

Cloud-first knowledge-to-skills pipeline. Capture insights from the web, curate thought-leader knowledge packs, and compile everything into Claude Code skills — available from any device, always on.

## What It Does

1. **Capture** — Clip from the web (via Obsidian Clipper or dashboard), LLM extracts structured capsules
2. **Curate** — Subscribe to leader packs (Karpathy, Levelsio, etc.) or build your own
3. **Compile** — Transform capsules into `.claude/skills/*.md` files that load at Claude Code session start
4. **Search** — MCP server gives Claude real-time access to your knowledge base

## Architecture

```
Obsidian Clipper / Dashboard / Extension
          ↓
    Cloud Backend (FastAPI + PostgreSQL)
          ↓
  ┌───────┼───────┐
  MCP    Skill    Web
 Server  Compiler Dashboard
```

## Quickstart

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)
- PostgreSQL 16+
- OpenAI API key

### Install

```bash
git clone https://github.com/your-org/neural-sieve-v3.git
cd neural-sieve-v3
uv sync --extra dev
```

### Configure

```bash
cp .env.example .env
# Edit .env with your values:
#   SIEVE_DATABASE_URL=postgresql+asyncpg://localhost:5432/neural_sieve_v3
#   SIEVE_JWT_SECRET=<generate-a-strong-secret>
#   SIEVE_OPENAI_API_KEY=sk-...
#   SIEVE_OPENAI_API_BASE=https://api.fuel1.ai/v1   # optional, default: OpenAI
#   SIEVE_GOOGLE_CLIENT_ID=...                       # optional, for Google sign-in
#   SIEVE_GOOGLE_CLIENT_SECRET=...
```

### Set Up Database

```bash
createdb neural_sieve_v3
uv run alembic upgrade head
```

### Run

```bash
# Start the API + dashboard
uv run sieve serve

# Open http://localhost:8421
```

### Create Your Account

```bash
# Via API
curl -X POST http://localhost:8421/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "your-password", "display_name": "Your Name"}'

# Save the api_key from the response — you'll need it for MCP + CLI
```

## Obsidian Integration

[Obsidian](https://obsidian.md/) is a powerful knowledge management app that stores notes as local Markdown files. Neural Sieve integrates with Obsidian via the **Web Clipper** browser extension to capture knowledge directly into your sieve.

### Setup

1. **Install Obsidian** — download from [obsidian.md](https://obsidian.md/)
2. **Install Obsidian Web Clipper** — get the browser extension from the [Chrome Web Store](https://chromewebstore.google.com/detail/obsidian-web-clipper/cnjifjpddelmedmihgijeibhnjfabmlf) or [Firefox Add-ons](https://addons.mozilla.org/en-US/firefox/addon/obsidian-web-clipper/)
3. **Configure the Clipper** — point it at your Neural Sieve capture endpoint (`/api/capture/`)

A dedicated Neural Sieve Obsidian plugin is planned for Phase 3, which will provide deeper two-way sync between your vault and your sieve.

## CLI Commands

```bash
uv run sieve version          # Show version
uv run sieve serve             # Start API server (default port 8421)
uv run sieve mcp               # Start MCP server for Claude Code
uv run sieve compile           # Compile capsules into Claude skills
uv run sieve compile --pack karpathy   # Compile one leader pack
uv run sieve compile --personal        # Compile personal capsules
uv run sieve compile --all             # Compile everything
```

## Connect to Claude Code

Add to your Claude Code MCP config (`.mcp.json` or settings):

```json
{
  "mcpServers": {
    "neural-sieve": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/neural-sieve-v3", "sieve", "mcp"],
      "env": {
        "SIEVE_API_URL": "https://your-app.fly.dev",
        "SIEVE_API_KEY": "your-api-key"
      }
    }
  }
}
```

Claude Code can now search your knowledge base, retrieve capsules, and access your pinned "eternal truths" during coding sessions.

## Compile Skills

After capturing knowledge, compile it into Claude Code skills:

```bash
# Set your API credentials
export SIEVE_API_URL=https://your-app.fly.dev
export SIEVE_API_KEY=your-api-key

# Compile all capsules into skills
uv run sieve compile --all --output .claude/skills

# Skills are now loaded automatically in Claude Code sessions
```

## Migrate from v1

If you have existing Neural Sieve v1 capsules:

```bash
uv run scripts/migrate_v1.py https://your-app.fly.dev your-api-key
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/signup` | Create account |
| POST | `/api/auth/login` | Get JWT token |
| GET | `/auth/google/login` | Google OAuth sign-in |
| GET | `/auth/google/callback` | Google OAuth callback |
| GET | `/api/auth/me` | Current user |
| GET | `/api/capsules/` | List capsules |
| POST | `/api/capsules/` | Create capsule |
| GET | `/api/capsules/{id}` | Get capsule |
| PUT | `/api/capsules/{id}` | Update capsule |
| DELETE | `/api/capsules/{id}` | Delete capsule |
| POST | `/api/capsules/search` | Search capsules |
| POST | `/api/capture/` | Capture from URL/text |

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy async, PostgreSQL 16
- **Frontend:** HTMX + Jinja2, responsive dark theme
- **Search:** LLM-ranked semantic search (pgvector planned)
- **MCP:** Model Context Protocol for Claude Code integration
- **Package Manager:** uv (mandatory)
- **Hosting:** Fly.io

## Project Structure

```
neural-sieve-v3/
├── src/sieve/
│   ├── api/              # FastAPI routes (auth, capsules, capture)
│   ├── compiler/         # Skill compiler (capsules → .claude/skills/)
│   ├── dashboard/        # Web UI (HTMX + Jinja2 templates)
│   ├── db/               # SQLAlchemy models + Alembic migrations
│   ├── llm/              # OpenAI integration (extraction, ranking)
│   ├── mcp/              # MCP server for Claude Code
│   ├── cli.py            # Click CLI entry point
│   └── config.py         # Pydantic settings
├── tests/                # 71 tests
├── scripts/              # Migration scripts
├── docs/plans/           # Design + implementation docs
└── pyproject.toml
```

## License

MIT

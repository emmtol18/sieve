# Neural Sieve v3

Cloud-first knowledge-to-skills pipeline. Capture insights from the web, curate your knowledge, and compile everything into Claude Code skills — available from any device, always on.

## What It Does

1. **Capture** — Clip from the web (via browser extension or dashboard), LLM extracts structured capsules
2. **Curate** — Build your sieve, follow others, and organize by category
3. **Compile** — Transform capsules into `.claude/skills/*.md` files that load at Claude Code session start
4. **Search** — MCP server gives Claude real-time access to your knowledge base

## Architecture

```
Browser Extension / Dashboard / Import
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
- LLM API key (BlackFuel or OpenAI-compatible)

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

## Import from Obsidian

You can import notes from your Obsidian vault:

1. Export your vault as a `.zip` file
2. Go to **Settings > Import** in the dashboard
3. Upload the zip — markdown files are parsed and captured as capsules

## CLI Commands

```bash
uv run sieve version          # Show version
uv run sieve serve             # Start API server (default port 8421)
uv run sieve mcp               # Start MCP server for Claude Code
uv run sieve compile                   # Compile one skill per capsule (default)
uv run sieve compile --by category     # Group by category
uv run sieve compile --by author       # Group by author
uv run sieve compile --all             # Include all capsules (not just skill-eligible)
```

## Connect to Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "neural-sieve": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/neural-sieve-v3", "sieve", "mcp"],
      "env": {
        "SIEVE_USER_EMAIL": "you@example.com",
        "SIEVE_DATABASE_URL": "your-database-url"
      }
    }
  }
}
```

Replace `/path/to/neural-sieve-v3` with your project directory and `your-database-url` with your PostgreSQL connection string.

Claude Code can now search your knowledge base, retrieve capsules, and access your pinned "eternal truths" during coding sessions. You can also configure this from the **Settings** page in the dashboard.

## Compile Skills

After capturing knowledge, compile it into Claude Code skills:

```bash
# Set your API credentials
export SIEVE_API_URL=https://your-app.fly.dev
export SIEVE_API_KEY=your-api-key

# Compile all capsules into skills (one per capsule)
uv run sieve compile --all --output .claude/skills

# Or group by author/category
uv run sieve compile --by author --all --output .claude/skills

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
| GET | `/api/skills/` | List skills |
| POST | `/api/skills/` | Create skill |
| GET | `/api/discover/sieves` | Discover public sieves |
| GET | `/api/discover/capsules` | Discover trending capsules |

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy async, PostgreSQL 16
- **Frontend:** HTMX + Jinja2, warm cream theme
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
├── tests/                # 195 tests
├── scripts/              # Migration scripts
├── docs/plans/           # Design + implementation docs
└── pyproject.toml
```

## License

MIT

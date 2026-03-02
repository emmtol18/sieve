# Neural Sieve v3

## Dev Commands
- `uv run sieve version` — verify install
- `uv run pytest` — run tests
- `uv run sieve serve` — start API server
- `uv run sieve mcp` — start MCP server
- `uv run sieve compile` — compile skills

## Package Manager
**uv is the ONLY package manager for this project.** Never use pip, pipenv, or poetry.
- `uv sync` — install deps
- `uv run <command>` — run anything
- `uv add <package>` — add a dependency

## LLM Backend
**BlackFuel API is the default LLM backend.** Base URL: `https://api.fuel1.ai/v1`, model: `openai/gpt-oss-120b:eu`.
Uses the `openai` Python SDK with custom base_url. API key env var: `SIEVE_OPENAI_API_KEY`.

## Conventions
- Python 3.12+, async/await throughout
- SQLAlchemy async ORM, Alembic migrations
- Pydantic v2 for all schemas
- uv as package manager (mandatory, see above)
- Tests with pytest-asyncio
- Dark theme for all frontend (HTMX + Jinja2)

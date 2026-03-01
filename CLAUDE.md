# Neural Sieve v3

## Dev Commands
- `uv run sieve version` — verify install
- `uv run pytest` — run tests
- `uv run sieve serve` — start API server
- `uv run sieve mcp` — start MCP server
- `uv run sieve compile` — compile skills

## Conventions
- Python 3.12+, async/await throughout
- SQLAlchemy async ORM, Alembic migrations
- Pydantic v2 for all schemas
- uv as package manager (mandatory)
- Tests with pytest-asyncio

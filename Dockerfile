FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ src/
COPY alembic.ini ./

EXPOSE 8421

CMD ["sh", "-c", "uv run alembic upgrade head && uv run sieve serve --port 8421"]

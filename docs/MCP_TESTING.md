# Testing the Neural Sieve MCP Server

This guide walks through verifying that the MCP server (the bridge between your
vault and an MCP client like **Claude Desktop** or **Claude Code**) works.

> **Provider note:** Claude is the *client* that connects to this server.
> Sieve's own LLM work (semantic search ranking, capsule extraction) uses the
> **OpenAI** API (`gpt-5-nano` / `gpt-5-mini`). The MCP server now starts even
> **without** an `OPENAI_API_KEY` — search just falls back to fast keyword
> matching instead of semantic ranking.

---

## TL;DR

```bash
uv pip install -e ".[dev]"          # 1. install
uv run pytest tests/ -m "not integration"   # 2. unit tests (no key needed)
uv run python scripts/smoke_test_mcp.py      # 3. end-to-end MCP smoke test (no key needed)
```

If all three are green, the server is healthy. To test *semantic* search and
the live OpenAI path, add a key and run the integration tests (step 4 below).

---

## The test plan

There are four layers, cheapest first. You can stop at whichever level you need.

| Level | What it proves | Needs OpenAI key? |
|-------|----------------|-------------------|
| 1. Unit tests | Scoring/parsing/config logic is correct | No |
| 2. Smoke test | The real server speaks MCP and search returns results | No |
| 3. Manual client | Claude Desktop / Code actually connects and calls tools | No (keyword) / Yes (semantic) |
| 4. Integration tests | The live OpenAI ranking call works | Yes |

### Level 1 — Unit tests

```bash
uv run pytest tests/ -m "not integration" -q
```

Covers keyword scoring, fallback normalization, category filtering, LLM
response parsing, and the new optional-key config behavior. No network, no key.

### Level 2 — Smoke test (end-to-end, no key)

```bash
uv run python scripts/smoke_test_mcp.py
```

This spawns the **real** `sieve mcp` server against a throwaway vault and drives
it over stdio exactly like Claude would. It asserts:

1. `initialize` handshake completes (server identifies as `neural-sieve`)
2. `tools/list` exposes all five tools
3. `get_pinned` returns a pinned capsule
4. `search_capsules("focus")` finds a tag-matched capsule **with no API key**
   (this is the regression that used to silently return nothing)
5. A non-matching query returns a clean "no results" message (no crash)
6. `get_categories` lists categories

Expected output ends with `OK: all MCP smoke checks passed.` and exit code `0`.

### Level 3 — Manual test from a real MCP client

1. Initialize a vault (skip if you already have one):
   ```bash
   mkdir ~/sieve-vault && cd ~/sieve-vault
   uv run --directory /path/to/neural-sieve sieve init
   ```
   Drop a few `.md` capsules into `Capsules/` (see the format in the main
   README), or copy the two from `scripts/smoke_test_mcp.py`.

2. Register the server with your client.

   **Claude Code** (from the vault directory):
   ```bash
   claude mcp add neural-sieve -- uv run --directory /absolute/path/to/your/vault sieve mcp
   ```
   Then in a session: `/mcp` should list `neural-sieve` as connected.

   **Claude Desktop** — edit
   `~/Library/Application Support/Claude/claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "neural-sieve": {
         "command": "uv",
         "args": ["run", "--directory", "/absolute/path/to/your/vault", "sieve", "mcp"]
       }
     }
   }
   ```
   Restart Claude Desktop. The 🔌 / tools icon should show the sieve tools.

3. Verify behavior in a chat:
   - Ask: *"Search my knowledge base for focus."* → it should call
     `search_capsules` and return your capsule.
   - Ask: *"What are my pinned eternal truths?"* → `get_pinned`.
   - With **no** `OPENAI_API_KEY`, results are labeled `keyword match`.
   - With a valid key in the vault's `.env`, results are labeled
     `semantic match` and surface conceptually related capsules.

### Level 4 — Integration tests (live OpenAI call)

Requires a real key in the vault's `.env` (`OPENAI_API_KEY=sk-...`):

```bash
uv run pytest tests/ -m integration -q
```

These confirm the ranking model returns parseable 0–10 scores and that the
token budget is sufficient. They are **skipped** automatically when no real key
is configured.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| Client shows server "failed" / "disconnected" | Wrong path in `--directory`. It must point at the **vault** folder. Test the exact command in a terminal first: `uv run --directory <path> sieve mcp` then type `Ctrl-D`. |
| Smoke test: "Server closed the connection" | The server crashed on startup. Run the command above manually and read the stderr traceback. |
| Search returns nothing even with matching capsules | Confirm the capsule has YAML frontmatter with a `title`; files without a title are skipped by the loader. |
| Search is slow / errors intermittently | The semantic path is hitting OpenAI. Check the key/quota, or remove the key to force fast keyword mode. |
| Where are the logs? | The server logs to **stderr** (stdout is reserved for JSON-RPC). Claude Desktop captures these under `~/Library/Logs/Claude/mcp-server-neural-sieve.log`. |

## What "working" looks like

- The server **starts and serves tools with or without** an OpenAI key.
- `search_capsules` returns relevant capsules in keyword mode and richer,
  concept-aware results in semantic mode.
- A bad/missing key degrades gracefully instead of taking the whole server down.

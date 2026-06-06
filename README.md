# Neural Sieve

> The High-Signal External Memory for AI Influence

Neural Sieve is a **filter, not a bucket**. It captures only "mind-blowing" insights—the 1% that change your perspective. It stores knowledge locally as plain-text **Knowledge Capsules**, making your wisdom accessible to any AI through context injection.

## Quick Start

### 1. Install

```bash
# Clone and enter directory
cd neural-sieve

# Install with uv
uv sync

# Create .env with your OpenAI API key
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 2. Initialize Vault

```bash
uv run sieve init
```

### 3. Start Neural Sieve

```bash
uv run sieve start
# Opens dashboard at http://127.0.0.1:8420
```

This starts both the file watcher and dashboard together. Drop files into `Inbox/` and they'll be automatically processed into capsules.

## CLI Commands

| Command | Description |
|---------|-------------|
| `sieve init` | Initialize vault in current directory |
| `sieve start` | Start watcher + dashboard together (recommended) |
| `sieve watch` | Start file watcher only |
| `sieve manage` | Start dashboard only (localhost:8420) |
| `sieve mcp` | Start MCP server for AI integration |
| `sieve process <file>` | Manually process a single file |
| `sieve index` | Regenerate knowledge index |

## Directory Structure

```
Neural-Sieve-Vault/
├── .sieve/                # Configuration and logs
├── Capsules/              # Knowledge capsules organized by category
│   ├── INDEX.md           # THE MAP: Auto-generated index of all capsules
│   ├── Technology/
│   ├── Business/
│   └── ...
├── Legacy/                # Deprecated capsules (moved here to reduce noise)
├── Assets/                # Original screenshots and files
│   └── 2026-01/
└── Inbox/                 # DROP ZONE: All raw captures land here
```

## Chrome Extension

1. Open `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked" → select the `extension/` folder
4. Make sure `sieve manage` is running

**Usage:**
- Select text → click extension → "Capture Selection"
- Right-click selected text → "Save to Neural Sieve"
- Click "Capture Full Page" for entire articles

## Configuration

### Environment Variables (.env)

```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Watch a screenshot folder (in addition to Inbox/)
SIEVE_SCREENSHOT_FOLDER=/Users/yourname/Desktop

# Optional: Custom port (default: 8420)
SIEVE_PORT=8420
```

## MCP Integration

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`)
or other MCP client, then restart the client:

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

`--directory` points at the vault folder you ran `sieve init` in, so the
server finds your capsules and `.env` no matter where the client launches it.
A copy of this config lives in `.mcp.example.json`.

> The MCP server starts even **without** an `OPENAI_API_KEY` - search simply
> falls back to fast keyword matching instead of semantic ranking. Add a key to
> your vault's `.env` to enable conceptual/semantic search.

**Available Resources (Passive Context):**

Resources are automatically available in the AI's context - no tool calls needed:

- `capsules://pinned` - Your "Eternal Truths" (pinned capsules) - always available as authoritative context
- `capsules://index` - Complete knowledge index showing all available capsules by category

**Available Tools (Active Retrieval):**
- `search_capsules(query)` - Search knowledge by keyword
- `get_pinned()` - Get all pinned "Eternal Truths"
- `get_capsule(id)` - Read a specific capsule
- `get_index()` - Get the full knowledge index
- `get_categories()` - List all categories

## Knowledge Capsule Format

Each capsule is a markdown file with YAML frontmatter:

```markdown
---
id: "2026-01-14-T100000"
title: "The Core Logic of Neural Sieve"
source_url: "https://example.com/article"
tags: [AI, Memory, Architecture]
category: "Technology"
status: "active"
pinned: false
captured_at: 2026-01-14
capture_method: "browser"
---

# Executive Summary

> A 2-sentence hook explaining why this matters.

# Core Insight

The single most important takeaway.

# Full Content

The complete, cleaned text.
```

---

*For architecture details, see [docs/architecture.md](docs/architecture.md)*

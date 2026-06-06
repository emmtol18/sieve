#!/usr/bin/env python
"""End-to-end smoke test for the Neural Sieve MCP server.

Spawns the real `sieve mcp` stdio server against a throwaway vault and drives
it over JSON-RPC exactly like an MCP client (Claude Desktop / Claude Code)
would. No OpenAI key required - this exercises the keyword-search path so it
runs anywhere.

Usage:
    uv run python scripts/smoke_test_mcp.py

Exit code 0 = all checks passed, 1 = something failed.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PINNED_CAPSULE = """\
---
title: Deep Work Techniques
id: 2026-01-14-T100000
category: Productivity
tags: [focus, deep-work]
captured_at: 2026-01-14T10:00:00
pinned: true
---
Block out 90-minute focus sessions with no notifications.
"""

OTHER_CAPSULE = """\
---
title: React Performance Tips
id: 2026-01-15-T110000
category: Technology
tags: [react, frontend]
captured_at: 2026-01-15T11:00:00
pinned: false
---
Memoize expensive components and avoid unnecessary re-renders.
"""


class MCPClient:
    """Minimal JSON-RPC client speaking to the server over stdio."""

    def __init__(self, vault: Path):
        env = dict(os.environ)
        env.pop("OPENAI_API_KEY", None)  # prove it works with no key
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "sieve.cli", "mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(vault),
            env=env,
            text=True,
        )

    def _send(self, obj: dict) -> None:
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def request(self, id_: int, method: str, params: dict | None = None) -> dict:
        """Send a request and return the response with the matching id."""
        self._send({"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}})
        while True:
            line = self.proc.stdout.readline()
            if not line:
                stderr = self.proc.stderr.read()
                raise RuntimeError(f"Server closed the connection. stderr:\n{stderr[-1000:]}")
            msg = json.loads(line)
            if msg.get("id") == id_:
                return msg

    def notify(self, method: str, params: dict | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def close(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def _text(resp: dict) -> str:
    """Pull the text payload out of a tools/call result."""
    return resp["result"]["content"][0]["text"]


def main() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}" + (f" - {detail}" if detail and not ok else ""))
        if not ok:
            failures.append(name)

    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp)
        capsules = vault / "Capsules"
        capsules.mkdir()
        (capsules / "2026-01-14-T100000.md").write_text(PINNED_CAPSULE)
        (capsules / "2026-01-15-T110000.md").write_text(OTHER_CAPSULE)

        print(f"Spawning MCP server (no OPENAI_API_KEY) against {vault} ...")
        client = MCPClient(vault)
        try:
            # 1. Handshake completes
            init = client.request(1, "initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "smoke-test", "version": "1.0"},
            })
            check("initialize handshake", init.get("result", {}).get("serverInfo", {}).get("name") == "neural-sieve")
            client.notify("notifications/initialized")

            # 2. Tools are advertised
            tools = client.request(2, "tools/list")
            names = {t["name"] for t in tools["result"]["tools"]}
            expected = {"search_capsules", "get_pinned", "get_capsule", "get_index", "get_categories"}
            check("tools/list exposes all tools", expected <= names, f"missing {expected - names}")

            # 3. Pinned capsules come back
            pinned = client.request(3, "tools/call", {"name": "get_pinned", "arguments": {}})
            check("get_pinned returns the pinned capsule", "Deep Work Techniques" in _text(pinned))

            # 4. Keyword search finds a tag match WITHOUT an LLM (the bug we fixed)
            search = client.request(4, "tools/call", {"name": "search_capsules", "arguments": {"query": "focus"}})
            search_text = _text(search)
            check("search 'focus' finds tagged capsule (keyword mode)",
                  "Deep Work Techniques" in search_text and "keyword match" in search_text,
                  repr(search_text[:120]))

            # 5. A non-matching query degrades cleanly (no crash, no false hit)
            miss = client.request(5, "tools/call", {"name": "search_capsules", "arguments": {"query": "xyzzy-nonexistent"}})
            check("search miss returns a clean 'no results' message", "No relevant capsules" in _text(miss))

            # 6. Category listing works
            cats = client.request(6, "tools/call", {"name": "get_categories", "arguments": {}})
            cats_text = _text(cats)
            check("get_categories lists categories", "Productivity" in cats_text and "Technology" in cats_text)
        finally:
            client.close()

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s) failed -> {', '.join(failures)}")
        return 1
    print("OK: all MCP smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

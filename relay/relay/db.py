"""SQLite database operations for the relay."""

import logging
import time
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    key_prefix TEXT NOT NULL,
    created_at REAL NOT NULL,
    last_used_at REAL,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_admin INTEGER NOT NULL DEFAULT 0,
    rate_limit INTEGER NOT NULL DEFAULT 60
);

CREATE TABLE IF NOT EXISTS captures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key_id INTEGER NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    url TEXT,
    source_url TEXT,
    title TEXT,
    image_data TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at REAL NOT NULL,
    acked_at REAL,
    FOREIGN KEY (api_key_id) REFERENCES api_keys(id)
);

CREATE TABLE IF NOT EXISTS rate_limit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key_id INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    FOREIGN KEY (api_key_id) REFERENCES api_keys(id)
);

CREATE INDEX IF NOT EXISTS idx_captures_status ON captures(status);
CREATE INDEX IF NOT EXISTS idx_captures_created ON captures(created_at);
CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX IF NOT EXISTS idx_rate_limit_key_ts ON rate_limit_log(api_key_id, timestamp);
"""


async def init_db(db_path: Path) -> None:
    """Create database tables."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)
        await db.commit()
    logger.info(f"[DB] Initialized database at {db_path}")


async def get_db(db_path: Path) -> aiosqlite.Connection:
    """Get a database connection."""
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def create_capture(
    db: aiosqlite.Connection,
    api_key_id: int,
    content: str,
    url: str | None,
    source_url: str | None,
    title: str | None,
    image_data: str | None,
) -> dict:
    """Insert a new capture and return it."""
    now = time.time()
    cursor = await db.execute(
        """INSERT INTO captures (api_key_id, content, url, source_url, title, image_data, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
        (api_key_id, content, url, source_url, title, image_data, now),
    )
    await db.commit()
    return {"id": cursor.lastrowid, "status": "pending", "created_at": now}


async def get_pending(db: aiosqlite.Connection, limit: int = 100) -> list[dict]:
    """Get pending captures ordered by creation time."""
    cursor = await db.execute(
        """SELECT id, content, url, source_url, title, image_data, created_at
           FROM captures WHERE status = 'pending'
           ORDER BY created_at ASC LIMIT ?""",
        (limit,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def ack_capture(db: aiosqlite.Connection, capture_id: int) -> bool:
    """Mark a capture as acknowledged. Returns True if found and updated."""
    now = time.time()
    cursor = await db.execute(
        "UPDATE captures SET status = 'acked', acked_at = ? WHERE id = ? AND status = 'pending'",
        (now, capture_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def count_pending(db: aiosqlite.Connection) -> int:
    """Count pending captures."""
    cursor = await db.execute("SELECT COUNT(*) FROM captures WHERE status = 'pending'")
    row = await cursor.fetchone()
    return row[0]


async def log_rate_limit(db: aiosqlite.Connection, api_key_id: int) -> None:
    """Record an API call for rate limiting."""
    await db.execute(
        "INSERT INTO rate_limit_log (api_key_id, timestamp) VALUES (?, ?)",
        (api_key_id, time.time()),
    )
    await db.commit()


async def check_rate_limit(db: aiosqlite.Connection, api_key_id: int, limit: int) -> bool:
    """Check if key is within rate limit (calls per hour). Returns True if allowed."""
    one_hour_ago = time.time() - 3600
    cursor = await db.execute(
        "SELECT COUNT(*) FROM rate_limit_log WHERE api_key_id = ? AND timestamp > ?",
        (api_key_id, one_hour_ago),
    )
    row = await cursor.fetchone()
    return row[0] < limit


async def cleanup_rate_limit_log(db: aiosqlite.Connection) -> None:
    """Remove rate limit entries older than 1 hour."""
    one_hour_ago = time.time() - 3600
    await db.execute("DELETE FROM rate_limit_log WHERE timestamp < ?", (one_hour_ago,))
    await db.commit()


async def store_api_key(
    db: aiosqlite.Connection,
    name: str,
    key_hash: str,
    key_prefix: str,
    is_admin: bool = False,
    rate_limit: int = 60,
) -> int:
    """Store a hashed API key. Returns the key ID."""
    now = time.time()
    cursor = await db.execute(
        """INSERT INTO api_keys (name, key_hash, key_prefix, created_at, is_admin, rate_limit)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name, key_hash, key_prefix, now, int(is_admin), rate_limit),
    )
    await db.commit()
    return cursor.lastrowid


async def find_key_by_prefix(db: aiosqlite.Connection, prefix: str) -> dict | None:
    """Find an API key record by its prefix."""
    cursor = await db.execute(
        "SELECT * FROM api_keys WHERE key_prefix = ? AND is_active = 1",
        (prefix,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def list_api_keys(db: aiosqlite.Connection) -> list[dict]:
    """List all API keys (without hashes)."""
    cursor = await db.execute(
        "SELECT id, name, key_prefix, created_at, last_used_at, is_active, is_admin, rate_limit "
        "FROM api_keys ORDER BY created_at DESC"
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def revoke_key(db: aiosqlite.Connection, key_prefix: str) -> bool:
    """Soft-delete an API key by prefix. Returns True if found."""
    cursor = await db.execute(
        "UPDATE api_keys SET is_active = 0 WHERE key_prefix = ?",
        (key_prefix,),
    )
    await db.commit()
    return cursor.rowcount > 0


async def update_key_last_used(db: aiosqlite.Connection, key_id: int) -> None:
    """Update last_used_at timestamp for a key."""
    await db.execute(
        "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
        (time.time(), key_id),
    )
    await db.commit()

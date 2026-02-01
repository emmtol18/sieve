"""Relay server configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class RelaySettings(BaseSettings):
    """Settings loaded from environment with RELAY_ prefix."""

    model_config = SettingsConfigDict(
        env_prefix="RELAY_",
        extra="ignore",
    )

    db_path: Path = Path("/opt/sieve-relay/data/relay.db")
    host: str = "127.0.0.1"
    port: int = 8421
    global_rate_limit: int = 200  # per hour, across all keys
    max_pending_captures: int = 1000

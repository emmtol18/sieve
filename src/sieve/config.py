"""Configuration management for Neural Sieve."""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SIEVE_",
        extra="ignore",
    )

    # OpenAI
    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    openai_model: str = "gpt-5-mini"

    # Paths (relative to vault root)
    vault_root: Path = Field(default_factory=Path.cwd)
    screenshot_folder: Optional[Path] = None

    # Server
    port: int = 8420
    host: str = "127.0.0.1"

    # Processing
    max_retries: int = 5
    retry_base_delay: float = 1.0

    @property
    def inbox_path(self) -> Path:
        return self.vault_root / "Inbox"

    @property
    def capsules_path(self) -> Path:
        return self.vault_root / "Capsules"

    @property
    def assets_path(self) -> Path:
        return self.vault_root / "Assets"

    @property
    def legacy_path(self) -> Path:
        return self.vault_root / "Legacy"

    @property
    def sieve_path(self) -> Path:
        return self.vault_root / ".sieve"

    @property
    def failed_path(self) -> Path:
        return self.inbox_path / "failed"

    @property
    def readme_path(self) -> Path:
        return self.vault_root / "README.md"

    @property
    def config_path(self) -> Path:
        return self.sieve_path / "config.yaml"

    @property
    def error_log_path(self) -> Path:
        return self.sieve_path / "error.log"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()

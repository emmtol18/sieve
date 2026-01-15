"""Tests for sieve.config module."""

from pathlib import Path

import pytest

from sieve.config import Settings, get_settings


class TestSettings:
    """Tests for Settings class."""

    def test_default_settings(self, monkeypatch):
        """Test Settings with minimal required values."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        settings = Settings(openai_api_key="test-key")

        assert settings.openai_api_key == "test-key"
        assert settings.openai_model == "gpt-5-mini"
        assert settings.port == 8420
        assert settings.host == "127.0.0.1"
        assert settings.max_retries == 5
        assert settings.retry_base_delay == 1.0

    def test_custom_vault_root(self, tmp_path, monkeypatch):
        """Test Settings with custom vault root."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        settings = Settings(
            openai_api_key="test-key",
            vault_root=tmp_path,
        )

        assert settings.vault_root == tmp_path
        assert settings.inbox_path == tmp_path / "Inbox"
        assert settings.capsules_path == tmp_path / "Capsules"
        assert settings.assets_path == tmp_path / "Assets"
        assert settings.legacy_path == tmp_path / "Legacy"
        assert settings.sieve_path == tmp_path / ".sieve"

    def test_path_properties(self, settings):
        """Test all path properties are derived correctly."""
        vault = settings.vault_root

        assert settings.inbox_path == vault / "Inbox"
        assert settings.capsules_path == vault / "Capsules"
        assert settings.assets_path == vault / "Assets"
        assert settings.legacy_path == vault / "Legacy"
        assert settings.sieve_path == vault / ".sieve"
        assert settings.failed_path == vault / "Inbox" / "failed"
        assert settings.index_path == vault / "Capsules" / "INDEX.md"
        assert settings.config_path == vault / ".sieve" / "config.yaml"
        assert settings.error_log_path == vault / ".sieve" / "error.log"

    def test_env_prefix(self, monkeypatch, tmp_path):
        """Test that SIEVE_ prefix works for environment variables."""
        monkeypatch.setenv("OPENAI_API_KEY", "env-api-key")
        monkeypatch.setenv("SIEVE_PORT", "9000")
        monkeypatch.setenv("SIEVE_HOST", "0.0.0.0")

        settings = Settings()

        assert settings.port == 9000
        assert settings.host == "0.0.0.0"

    def test_openai_api_key_from_env(self, monkeypatch):
        """Test that OPENAI_API_KEY can be loaded from environment."""
        monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")
        settings = Settings()

        assert settings.openai_api_key == "env-openai-key"


class TestGetSettings:
    """Tests for get_settings factory function."""

    def test_get_settings_returns_settings_instance(self, monkeypatch):
        """Test that get_settings returns a Settings instance."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        settings = get_settings()

        assert isinstance(settings, Settings)
        assert settings.openai_api_key == "test-key"

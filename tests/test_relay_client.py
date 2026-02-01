"""Tests for the relay pull client."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sieve.config import Settings
from sieve.relay_client import RelayClient


@pytest.fixture
def relay_settings(tmp_path: Path, monkeypatch) -> Settings:
    """Settings with relay configured."""
    vault = tmp_path / "vault"
    vault.mkdir()
    for d in ("Inbox", "Capsules", "Assets", "Legacy", ".sieve"):
        (vault / d).mkdir()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    return Settings(
        vault_root=vault,
        openai_api_key="test-key",
        relay_url="https://relay.example.com",
        relay_admin_key="sieve_live_testkey1234567890abcdef",
        relay_pull_interval=10,
    )


@pytest.fixture
def relay_client(relay_settings: Settings) -> RelayClient:
    return RelayClient(relay_settings)


class TestRelayClient:
    def test_init(self, relay_client):
        assert relay_client.base_url == "https://relay.example.com"
        assert "Bearer sieve_live_" in relay_client.headers["Authorization"]

    async def test_fetch_pending(self, relay_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "captures": [
                {"id": 1, "content": "test", "url": None, "source_url": None,
                 "title": None, "image_data": None, "created_at": 1700000000},
            ],
            "count": 1,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("sieve.relay_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            captures = await relay_client.fetch_pending()
            assert len(captures) == 1
            assert captures[0]["id"] == 1

    async def test_ack_capture(self, relay_client):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("sieve.relay_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await relay_client.ack_capture(1)
            assert result is True

    async def test_pull_and_process(self, relay_client):
        """Full pull-process-ack cycle with mocked HTTP and processor."""
        mock_processor = MagicMock()
        mock_processor.process_browser_capture = AsyncMock(return_value=Path("/fake/capsule.md"))

        relay_client.fetch_pending = AsyncMock(return_value=[
            {"id": 1, "content": "article text", "url": None,
             "source_url": "https://example.com", "title": "Test", "image_data": None},
            {"id": 2, "content": "", "url": "https://example.com/page",
             "source_url": None, "title": None, "image_data": None},
        ])
        relay_client.ack_capture = AsyncMock(return_value=True)

        count = await relay_client.pull_and_process(mock_processor)

        assert count == 2
        assert mock_processor.process_browser_capture.call_count == 2
        assert relay_client.ack_capture.call_count == 2

    async def test_pull_and_process_empty(self, relay_client):
        """No pending captures returns 0."""
        mock_processor = MagicMock()
        relay_client.fetch_pending = AsyncMock(return_value=[])

        count = await relay_client.pull_and_process(mock_processor)
        assert count == 0

    async def test_pull_and_process_partial_failure(self, relay_client):
        """Processing failure for one capture doesn't block others."""
        mock_processor = MagicMock()
        mock_processor.process_browser_capture = AsyncMock(
            side_effect=[Exception("LLM error"), Path("/fake/capsule.md")]
        )

        relay_client.fetch_pending = AsyncMock(return_value=[
            {"id": 1, "content": "fail", "url": None,
             "source_url": None, "title": None, "image_data": None},
            {"id": 2, "content": "succeed", "url": None,
             "source_url": None, "title": None, "image_data": None},
        ])
        relay_client.ack_capture = AsyncMock(return_value=True)

        count = await relay_client.pull_and_process(mock_processor)

        # Only the successful one should be acked
        assert count == 1
        relay_client.ack_capture.assert_called_once_with(2)

    async def test_pull_and_process_fetch_error(self, relay_client):
        """HTTP error during fetch returns 0."""
        import httpx

        mock_processor = MagicMock()
        relay_client.fetch_pending = AsyncMock(
            side_effect=httpx.ConnectError("connection refused")
        )

        count = await relay_client.pull_and_process(mock_processor)
        assert count == 0

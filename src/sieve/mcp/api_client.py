"""Minimal MCP API client for Neural Sieve v3."""

import httpx


class SieveAPIClient:
    """HTTP client for the Neural Sieve API."""

    def __init__(self, api_url: str, api_key: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    async def list_capsules(self, limit: int = 50) -> dict:
        """Fetch capsules from the API."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            resp = await client.get(
                f"{self.api_url}/api/capsules",
                params={"limit": limit},
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def search_capsules(self, query: str, limit: int = 10) -> dict:
        """Search capsules via the API."""
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            resp = await client.post(
                f"{self.api_url}/api/capsules/search",
                json={"query": query, "limit": limit},
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()

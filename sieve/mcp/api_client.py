"""HTTP client for the Neural Sieve cloud API."""

import httpx


class SieveAPIClient:
    """HTTP client for the Neural Sieve cloud API.

    Connects to the Neural Sieve API server and provides methods for
    searching, retrieving, and listing capsules.
    """

    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def search_capsules(self, query: str, limit: int = 10, **filters) -> dict:
        """Semantic search across capsules."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.api_url}/api/capsules/search",
                json={"query": query, "limit": limit, **filters},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def get_capsule(self, capsule_id: str) -> dict:
        """Get a specific capsule by ID."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.api_url}/api/capsules/{capsule_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def list_capsules(self, **params) -> dict:
        """List capsules with optional filters."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.api_url}/api/capsules/",
                params=params,
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def get_pinned(self) -> dict:
        """Get all pinned capsules.

        Fetches all capsules and filters client-side since the list
        endpoint doesn't yet support a pinned filter.
        """
        data = await self.list_capsules(limit=200)
        capsules = [c for c in data.get("capsules", []) if c.get("pinned")]
        return {"capsules": capsules, "total": len(capsules)}

    async def get_index(self) -> dict:
        """Get full knowledge index (all capsules)."""
        return await self.list_capsules(limit=200)

    async def list_skills(self, **params) -> dict:
        """List skills with optional filters."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.api_url}/api/skills/",
                params=params,
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def get_skill(self, skill_id: str) -> dict:
        """Get a specific skill by ID."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.api_url}/api/skills/{skill_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

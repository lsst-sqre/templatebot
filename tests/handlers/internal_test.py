"""Test the internal API handlers."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from templatebot.config import config


@pytest.mark.asyncio
async def test_get_index(client: AsyncClient) -> None:
    """Test ``GET /``."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == config.name
    assert isinstance(data["version"], str)
    assert isinstance(data["description"], str)
    assert isinstance(data["repository_url"], str)
    assert isinstance(data["documentation_url"], str)

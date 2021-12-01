import pytest

from templatebot.app import create_app


@pytest.fixture
async def client(aiohttp_client):
    app = create_app()
    client = await aiohttp_client(app)
    return client

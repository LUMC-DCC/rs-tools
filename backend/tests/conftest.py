from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fakeredis.aioredis
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from rs_tools.config import Settings
from rs_tools.main import create_app
from rs_tools.storage.redis import RedisWorkspaceStore


@dataclass
class TestContext:
    """Everything a route test needs to drive and inspect one application."""

    __test__ = False

    client: AsyncClient
    app: FastAPI
    redis: fakeredis.aioredis.FakeRedis
    store: RedisWorkspaceStore


@pytest.fixture
async def context(tmp_path: Path) -> TestContext:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    store = RedisWorkspaceStore(redis, ttl_seconds=60)
    settings = Settings(
        redis_url="redis://unused/0",
        workspace_ttl_seconds=60,
        max_request_bytes=1_048_576,
        public_base_url=None,
        frontend_dist=tmp_path / "missing-frontend",
        cors_origins=(),
    )
    app = create_app(settings=settings, store=store)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield TestContext(client=client, app=app, redis=redis, store=store)
    await redis.aclose()

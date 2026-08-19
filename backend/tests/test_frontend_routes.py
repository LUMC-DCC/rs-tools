from pathlib import Path

import fakeredis.aioredis
from httpx import ASGITransport, AsyncClient

from rs_tools.config import Settings
from rs_tools.main import create_app
from rs_tools.storage.redis import RedisWorkspaceStore


async def test_built_frontend_and_client_routes_serve_index(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<h1>built frontend</h1>", encoding="utf-8")
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    store = RedisWorkspaceStore(redis, ttl_seconds=60)
    app = create_app(
        settings=Settings(
            redis_url="redis://unused/0",
            workspace_ttl_seconds=60,
            max_request_bytes=1_048_576,
            public_base_url=None,
            frontend_dist=dist,
            cors_origins=(),
        ),
        store=store,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        homepage = await client.get("/")
        homepage_head = await client.head("/")
        workspace = await client.get("/w/example-id")
        client_route = await client.get("/future/client-route")
        missing_api = await client.get("/api/not-a-route")

    assert homepage.status_code == 200
    assert homepage_head.status_code == 200
    assert workspace.text == homepage.text
    assert client_route.text == homepage.text
    assert missing_api.status_code == 404
    await redis.aclose()

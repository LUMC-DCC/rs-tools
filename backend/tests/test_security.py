"""Checks for the safeguards a public deployment depends on."""

from __future__ import annotations

import re
from pathlib import Path

import fakeredis.aioredis
import pytest
from conftest import TestContext
from httpx import ASGITransport, AsyncClient

from rs_tools.config import Settings
from rs_tools.main import create_app
from rs_tools.storage.redis import RedisWorkspaceStore


async def test_every_response_carries_security_headers(context: TestContext) -> None:
    response = await context.client.get("/api/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    # Sent only for an HTTPS deployment; pinning a browser to a scheme this
    # deployment does not serve would lock users out.
    assert "strict-transport-security" not in response.headers


async def test_rejected_requests_carry_security_headers_too(context: TestContext) -> None:
    # The headers are only a guarantee if they survive the middleware that
    # refuse a request before any handler runs.
    response = await context.client.post(
        "/api/workspaces",
        content=b"x" * 1_048_577,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" in response.headers


async def test_workspace_identifiers_must_look_like_uuids(context: TestContext) -> None:
    response = await context.client.get("/api/workspaces/not-a-uuid")

    assert response.status_code == 422


async def test_expensive_endpoints_are_rate_limited(tmp_path: Path) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    store = RedisWorkspaceStore(redis, ttl_seconds=60)
    app = create_app(
        settings=Settings(
            redis_url="redis://unused/0",
            workspace_ttl_seconds=60,
            max_request_bytes=1_048_576,
            public_base_url=None,
            frontend_dist=tmp_path / "missing-frontend",
            cors_origins=(),
            rate_limit_heavy_requests=2,
        ),
        store=store,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = (await client.post("/api/workspaces/empty")).json()
        path = f"/api/workspaces/{created['id']}/generators/license"
        statuses = [(await client.get(path)).status_code for _ in range(3)]

    assert statuses[-1] == 429
    await redis.aclose()


async def test_rate_limiting_does_not_take_the_service_down_with_it(
    context: TestContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing_counter(_key: str, _ttl_seconds: int) -> int:
        raise ConnectionError("counter store unavailable")

    monkeypatch.setattr(context.store, "increment_with_expiry", failing_counter)

    response = await context.client.post("/api/workspaces/empty")

    assert response.status_code == 201


async def test_unreachable_storage_reports_not_ready(
    context: TestContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing_ping() -> bool:
        raise ConnectionError("redis is unreachable")

    monkeypatch.setattr(context.store, "ping", failing_ping)

    response = await context.client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["detail"] == "Storage is unavailable."


async def test_untrusted_host_headers_are_refused(tmp_path: Path) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    store = RedisWorkspaceStore(redis, ttl_seconds=60)
    app = create_app(
        settings=Settings(
            redis_url="redis://unused/0",
            workspace_ttl_seconds=60,
            max_request_bytes=1_048_576,
            public_base_url="https://rs-tools.example.org",
            frontend_dist=tmp_path / "missing-frontend",
            cors_origins=(),
            trusted_hosts=("rs-tools.example.org",),
        ),
        store=store,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        allowed = await client.get("/api/health", headers={"Host": "rs-tools.example.org"})
        forged = await client.get("/api/health", headers={"Host": "attacker.example"})

    assert allowed.status_code == 200
    assert forged.status_code == 400
    assert forged.headers["x-content-type-options"] == "nosniff"
    await redis.aclose()


def test_github_flow_needs_a_configured_public_base_url() -> None:
    credentials = {
        "github_client_id": "Ov23li.test",
        "github_client_secret": "client-secret",
        "github_cookie_secret": "cookie-secret-with-enough-randomness",
    }

    # Without it, the OAuth callback URL could only come from the request's Host
    # header, which any client can set.
    assert not Settings(public_base_url=None, **credentials).github_configured
    assert Settings(public_base_url="https://rs-tools.example.org", **credentials).github_configured


def test_the_public_surface_stays_inside_the_api_namespace(tmp_path: Path) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app = create_app(
        settings=Settings(
            redis_url="redis://unused/0",
            frontend_dist=tmp_path / "missing-frontend",
            cors_origins=(),
        ),
        store=RedisWorkspaceStore(redis, ttl_seconds=60),
    )

    # Everything is either under /api or one of the two routes that serve the
    # single-page application. A new path outside that set is surface nobody
    # decided to publish, so it fails here rather than in a deployment.
    paths = {route.path for route in app.routes if getattr(route, "methods", None)}
    unexpected = {path for path in paths if not path.startswith("/api")} - {"/", "/{path:path}"}

    assert unexpected == set()


async def test_repository_visibility_must_be_stated(context: TestContext) -> None:
    created = (await context.client.post("/api/workspaces/empty")).json()

    # Visibility is not something to inherit from a default: a caller that omits
    # it is asked, rather than having a repository published on a guess.
    response = await context.client.post(
        f"/api/workspaces/{created['id']}/github/repositories",
        json={"owner": "octocat", "name": "example"},
    )

    assert response.status_code == 422


async def test_the_catalogue_endpoints_are_rate_limited(tmp_path: Path) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app = create_app(
        settings=Settings(
            redis_url="redis://unused/0",
            frontend_dist=tmp_path / "missing-frontend",
            cors_origins=(),
            rate_limit_requests=2,
        ),
        store=RedisWorkspaceStore(redis, ttl_seconds=60),
    )

    # These serve the largest documents the service has. Left unlimited, asking
    # for them in a loop is the cheapest way to spend its CPU.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        statuses = [(await client.get("/api/generators")).status_code for _ in range(3)]

    assert statuses[-1] == 429
    await redis.aclose()


async def test_the_catalogue_is_built_once_rather_than_per_request(
    context: TestContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the catalogue must not be rebuilt while serving a request")

    # Resolving a generator's fields walks the schema for every field it
    # declares. Startup is the only place that may pay for it.
    monkeypatch.setattr("rs_tools.main.build_catalogue", fail)

    first = await context.client.get("/api/generators")
    second = await context.client.get("/api/generators")

    assert first.status_code == 200
    assert first.content == second.content
    assert len(first.json()) > 0


async def test_a_malformed_oauth_state_is_rejected_rather_than_crashing(tmp_path: Path) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app = create_app(
        settings=Settings(
            redis_url="redis://unused/0",
            frontend_dist=tmp_path / "missing-frontend",
            cors_origins=(),
            public_base_url="https://rs-tools.example.org",
            github_client_id="Ov23li.test",
            github_client_secret="client-secret",
            github_cookie_secret="cookie-secret-with-enough-randomness",
        ),
        store=RedisWorkspaceStore(redis, ttl_seconds=60),
    )

    # The state is compared with `compare_digest`, which refuses non-ASCII text.
    # Comparing as bytes keeps a junk callback a rejection instead of a 500.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"rs_tools_github_state": "whatever"},
    ) as client:
        response = await client.get(
            "/api/github/callback",
            params={"code": "temporary-code", "state": "é" * 8},
        )

    assert response.status_code == 400
    await redis.aclose()


def test_the_page_and_its_policy_reference_no_third_party_origin() -> None:
    from rs_tools.middleware import CONTENT_SECURITY_POLICY

    frontend = Path(__file__).resolve().parents[2] / "frontend"
    markup = (frontend / "index.html").read_text(encoding="utf-8")

    # The interface must talk to this origin and no other: a font CDN, an
    # analytics tag, or a script host would each hand every visitor's address to
    # a third party. Fonts are bundled instead, so nothing needs an exception.
    #
    # Dev cannot catch a mismatch between the two: Vite serves the page there
    # and applies no policy at all, so a third-party asset loads locally and is
    # silently blocked in production.
    external_in_markup = set(re.findall(r"https?://[^\"'\s>]+", markup))
    assert not external_in_markup, f"index.html references {external_in_markup}"

    external_in_policy = set(re.findall(r"https?://[^\s;]+", CONTENT_SECURITY_POLICY))
    assert not external_in_policy, f"the policy allows {external_in_policy}"


async def test_a_wildcard_host_matches_subdomains_without_admitting_look_alikes(
    tmp_path: Path,
) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app = create_app(
        settings=Settings(
            redis_url="redis://unused/0",
            frontend_dist=tmp_path / "missing-frontend",
            cors_origins=(),
            trusted_hosts=("*.onrender.com",),
        ),
        store=RedisWorkspaceStore(redis, ttl_seconds=60),
    )

    # A managed host assigns the hostname when the service is created, so a
    # deployment cannot name it in advance and has to trust the whole subdomain.
    # That must not stretch to a domain that merely ends with the same letters.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        accepted = {
            host: (await client.get("/api/health", headers={"Host": host})).status_code
            for host in ("rs-tools.onrender.com", "rs-tools-a1b2.onrender.com")
        }
        refused = {
            host: (await client.get("/api/health", headers={"Host": host})).status_code
            for host in ("onrender.com", "evil-onrender.com", "attacker.example")
        }

    assert set(accepted.values()) == {200}, accepted
    assert set(refused.values()) == {400}, refused
    await redis.aclose()

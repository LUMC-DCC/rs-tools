from __future__ import annotations

from typing import Any

import httpx
import pytest

from rs_tools.config import Settings
from rs_tools.generators.base import GeneratorInputError
from rs_tools.generators.repository import GeneratedRepository, RepositoryFile
from rs_tools.github import (
    GitHubAccount,
    GitHubAPIError,
    GitHubConnection,
    GitHubOAuthService,
    _github_response,
    enrich_repository_urls,
    repository_metadata,
)


def github_service() -> GitHubOAuthService:
    return GitHubOAuthService(
        Settings(
            public_base_url="https://rs-tools.example.org",
            github_client_id="Ov23li.test",
            github_client_secret="client-secret",
            github_cookie_secret="cookie-secret-with-enough-randomness",
        )
    )


def test_github_authorization_state_is_encrypted_and_workspace_bound() -> None:
    service = github_service()

    authorization_url, state = service.begin_authorization(
        "workspace-id",
        "https://rs-tools.example.org/api/github/callback",
    )

    assert "github.com/login/oauth/authorize" in authorization_url
    assert "scope=repo+workflow+read%3Aorg" in authorization_url
    assert "code_challenge_method=S256" in authorization_url
    assert "workspace-id" not in state
    payload = service._decrypt(state)
    assert payload["workspace_id"] == "workspace-id"
    assert payload["code_verifier"] not in authorization_url


def test_github_validation_errors_include_safe_structured_details() -> None:
    response = httpx.Response(
        422,
        json={
            "message": "Validation Failed",
            "errors": [
                {
                    "resource": "Repository",
                    "field": "name",
                    "code": "custom",
                    "message": "name already exists on this account",
                }
            ],
        },
    )

    with pytest.raises(
        GitHubAPIError,
        match=r"HTTP 422.*name already exists on this account \(Repository\.name\)",
    ):
        _github_response(response, "GitHub could not create the repository")


def test_repository_metadata_uses_description_homepage_and_safe_topics() -> None:
    metadata = repository_metadata(
        {
            "project_short_description": "A research tool.",
            "urls": {"homepage": "https://example.org/tool"},
            "keywords": {"entries": ["Research Software", "Python", "research software", "C++"]},
        }
    )

    assert metadata.description == "A research tool."
    assert metadata.homepage == "https://example.org/tool"
    assert metadata.topics == ("research-software", "python", "c")


def test_github_destination_fills_missing_repository_and_deployed_docs_urls() -> None:
    original = {
        "project_slug": "research-tool",
        "documentation_builder": "zensical",
        "documentation_types": {"entries": ["user"]},
        "urls": {"repository": "", "homepage": "", "documentation": ""},
    }

    enriched = enrich_repository_urls(original, "LUMC-DCC", "research-tool")

    assert original["urls"]["repository"] == ""
    assert enriched["urls"] == {
        "repository": "https://github.com/LUMC-DCC/research-tool",
        "homepage": "",
        "documentation": "https://LUMC-DCC.github.io/research-tool/",
    }
    assert repository_metadata(enriched).homepage == ("https://LUMC-DCC.github.io/research-tool/")


def test_github_destination_preserves_explicit_urls_and_does_not_guess_plain_docs() -> None:
    explicit = enrich_repository_urls(
        {
            "documentation_types": {"entries": ["user"]},
            "urls": {
                "repository": "https://example.org/source",
                "documentation": "https://docs.example.org/tool",
            },
        },
        "octocat",
        "tool",
    )
    plain = enrich_repository_urls(
        {"documentation_types": {"entries": ["user"]}},
        "octocat",
        "tool",
    )
    r_project = enrich_repository_urls(
        {
            "documentation_builder": "pkgdown",
            "documentation_types": {"entries": ["user"]},
        },
        "octocat",
        "tool",
        "r",
    )

    assert explicit["urls"] == {
        "repository": "https://example.org/source",
        "documentation": "https://docs.example.org/tool",
    }
    assert plain["urls"] == {"repository": "https://github.com/octocat/tool"}
    assert r_project["urls"] == {"repository": "https://github.com/octocat/tool"}


@pytest.mark.asyncio
async def test_github_revocation_sends_delete_with_json_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = github_service()
    captured: dict[str, Any] = {}

    class FakeClient:
        async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
            captured.update(method=method, url=url, **kwargs)
            return httpx.Response(204)

    monkeypatch.setattr(service, "_client", FakeClient())

    revoked = await service.revoke_authorization(
        GitHubConnection("workspace-id", "oauth-token", 1, "octocat")
    )

    assert revoked is True
    assert captured["method"] == "DELETE"
    assert captured["json"] == {"access_token": "oauth-token"}


@pytest.mark.asyncio
async def test_github_accounts_include_user_and_organizations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = github_service()

    async def fake_request(
        _token: str,
        _method: str,
        path: str,
        _body: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        assert path == "/user/orgs?per_page=100"
        return [{"login": "LUMC-DCC", "id": 2}]

    monkeypatch.setattr(service, "_request", fake_request)
    accounts = await service.list_accounts(GitHubConnection("workspace-id", "token", 1, "octocat"))

    assert accounts == [
        GitHubAccount(login="octocat", type="User", account_id=1),
        GitHubAccount(login="LUMC-DCC", type="Organization", account_id=2),
    ]


@pytest.mark.asyncio
async def test_github_authorization_uses_pkce_and_checks_scopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = github_service()
    callback_url = "https://rs-tools.example.org/api/github/callback"
    _, state = service.begin_authorization("workspace-id", callback_url)
    exchanged: dict[str, str] = {}

    async def fake_exchange(code: str, callback: str, verifier: str) -> dict[str, str]:
        exchanged.update(code=code, callback=callback, verifier=verifier)
        return {
            "access_token": "oauth-token",
            "scope": "repo,workflow,read:org",
        }

    async def fake_request(
        token: str,
        method: str,
        path: str,
        _body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert (token, method, path) == ("oauth-token", "GET", "/user")
        return {"id": 1, "login": "octocat"}

    monkeypatch.setattr(service, "_exchange_code", fake_exchange)
    monkeypatch.setattr(service, "_request", fake_request)

    workspace_id, cookie = await service.complete_authorization(
        "temporary-code", state, state, callback_url
    )

    assert workspace_id == "workspace-id"
    assert exchanged == {
        "code": "temporary-code",
        "callback": callback_url,
        "verifier": service._decrypt(state)["code_verifier"],
    }
    assert service.read_connection(cookie, workspace_id).access_token == "oauth-token"


@pytest.mark.asyncio
async def test_github_publish_creates_one_tree_and_initial_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = github_service()
    requests: list[tuple[str, str, str, dict[str, Any] | None]] = []

    async def fake_request(
        _token: str,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        requests.append((_token, method, path, body))
        if path == "/user/repos":
            return {
                "owner": {"login": "octocat"},
                "name": "research-tool",
                "html_url": "https://github.com/octocat/research-tool",
                "default_branch": "main",
            }
        if path.endswith("/git/blobs"):
            return {"sha": f"blob-{len(requests)}"}
        if path.endswith("/git/trees"):
            return {"sha": "tree-sha"}
        if path.endswith("/git/commits"):
            return {"sha": "commit-sha"}
        return {}

    monkeypatch.setattr(service, "_request", fake_request)

    repository = GeneratedRepository(
        name="research-tool",
        files=(
            RepositoryFile(path="README.md", content=b"# Research tool\n"),
            RepositoryFile(path="bin/run", content=b"#!/bin/sh\n", executable=True),
        ),
    )

    url = await service.publish_repository(
        GitHubConnection(
            workspace_id="workspace-id",
            access_token="token",
            user_id=1,
            user_login="octocat",
        ),
        GitHubAccount(login="octocat", type="User", account_id=1),
        repository,
        "research-tool",
        False,
        "A generated repository.",
        "https://example.org/tool",
        ("research-software", "python"),
    )

    assert url == "https://github.com/octocat/research-tool"
    tree_request = next(body for _, _, path, body in requests if path.endswith("/git/trees"))
    assert tree_request is not None
    assert [entry["mode"] for entry in tree_request["tree"]] == ["100644", "100755"]
    create_request = next(body for _, _, path, body in requests if path == "/user/repos")
    assert create_request is not None
    assert create_request["auto_init"] is True
    assert create_request["homepage"] == "https://example.org/tool"
    topics_request = next(body for _, _, path, body in requests if path.endswith("/topics"))
    assert topics_request == {"names": ["research-software", "python"]}
    ref_request = next(
        (method, body)
        for _, method, path, body in requests
        if path.endswith("/git/refs/heads/main")
    )
    assert ref_request == ("PATCH", {"sha": "commit-sha", "force": True})
    commit_request = next(body for _, _, path, body in requests if path.endswith("/git/commits"))
    assert commit_request is not None
    assert "parents" not in commit_request
    assert next(token for token, _, path, _ in requests if path == "/user/repos") == "token"
    assert all(token == "token" for token, _, _, _ in requests)


@pytest.mark.asyncio
async def test_github_publish_rejects_unsafe_output_before_creating_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = github_service()

    async def unexpected_request(*_args: object, **_kwargs: object) -> dict[str, Any]:
        pytest.fail("GitHub must not be called for unsafe generated output")

    monkeypatch.setattr(service, "_request", unexpected_request)
    repository = GeneratedRepository(
        name="research-tool",
        files=(RepositoryFile(path="../.env", content=b"TOKEN=secret\n"),),
    )

    with pytest.raises(GeneratorInputError, match="unsafe path"):
        await service.publish_repository(
            GitHubConnection(
                workspace_id="workspace-id",
                access_token="token",
                user_id=1,
                user_login="octocat",
            ),
            GitHubAccount(login="octocat", type="User", account_id=1),
            repository,
            "research-tool",
            True,
            "A generated repository.",
        )

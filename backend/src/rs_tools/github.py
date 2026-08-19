"""Temporary GitHub OAuth connection and repository publishing service.

The connection is deliberately short-lived: the access token never reaches Redis
or workspace data, it lives only inside an encrypted HttpOnly cookie, and the
service attempts to revoke the whole OAuth grant after publishing succeeds.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
from cryptography.fernet import Fernet, InvalidToken

from rs_tools.config import Settings
from rs_tools.generators.repository import GeneratedRepository, validate_repository

GITHUB_CONNECTION_COOKIE = "rs_tools_github_connection"
GITHUB_STATE_COOKIE = "rs_tools_github_state"
GITHUB_STATE_MAX_AGE_SECONDS = 10 * 60
GITHUB_CONNECTION_MAX_AGE_SECONDS = 8 * 60 * 60
GITHUB_OAUTH_SCOPES = ("repo", "workflow", "read:org")
SAFE_GITHUB_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
MAX_GITHUB_TOPICS = 20
MAX_GITHUB_TOPIC_LENGTH = 50
GITHUB_PAGES_BUILDERS = frozenset({"mkdocs", "sphinx", "zensical"})


@dataclass(frozen=True, slots=True)
class GitHubRepositoryMetadata:
    """Repository metadata derived from an RSM document."""

    description: str
    homepage: str | None
    topics: tuple[str, ...]


def enrich_repository_urls(
    smp: dict[str, Any],
    owner: str,
    name: str,
    template_id: str | None = None,
) -> dict[str, Any]:
    """Fill GitHub URLs that become known only when a destination is chosen.

    Existing metadata always wins. A documentation URL is inferred only when
    the selected project configuration generates a site and a GitHub Pages
    deployment workflow.
    """
    enriched = deepcopy(smp)
    current_urls = enriched.get("urls")
    urls = dict(current_urls) if isinstance(current_urls, dict) else {}
    if not _nonempty_string(urls.get("repository")):
        urls["repository"] = f"https://github.com/{owner}/{name}"
    if not _nonempty_string(urls.get("documentation")) and _deploys_documentation(
        enriched, template_id
    ):
        suffix = "" if name.casefold() == f"{owner.casefold()}.github.io" else f"/{name}"
        urls["documentation"] = f"https://{owner}.github.io{suffix}/"
    enriched["urls"] = urls
    return enriched


def _deploys_documentation(smp: dict[str, Any], template_id: str | None) -> bool:
    documentation_types = smp.get("documentation_types")
    entries = documentation_types.get("entries") if isinstance(documentation_types, dict) else None
    return (
        (template_id or "python") == "python"
        and bool(entries)
        and smp.get("documentation_builder") in GITHUB_PAGES_BUILDERS
    )


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def repository_metadata(smp: dict[str, Any]) -> GitHubRepositoryMetadata:
    """Extract safe GitHub repository metadata from RSM fields."""
    description = smp.get("project_short_description")
    urls = smp.get("urls")
    homepage = None
    if isinstance(urls, dict):
        homepage = urls.get("homepage") or urls.get("documentation")
    # RSM permits URI references, while GitHub's sidebar needs a public web URL.
    if not isinstance(homepage, str) or urlsplit(homepage).scheme not in {"http", "https"}:
        homepage = None

    keywords = smp.get("keywords")
    entries = keywords.get("entries") if isinstance(keywords, dict) else None
    topics: list[str] = []
    if isinstance(entries, list):
        for keyword in entries:
            if not isinstance(keyword, str):
                continue
            topic = re.sub(r"[^a-z0-9]+", "-", keyword.casefold()).strip("-")
            topic = topic[:MAX_GITHUB_TOPIC_LENGTH].rstrip("-")
            if topic and topic not in topics:
                topics.append(topic)
            if len(topics) == MAX_GITHUB_TOPICS:
                break

    return GitHubRepositoryMetadata(
        description=description if isinstance(description, str) else "",
        homepage=homepage,
        topics=tuple(topics),
    )


class GitHubNotConfiguredError(RuntimeError):
    """The optional GitHub integration is not configured on this deployment."""


class GitHubConnectionError(ValueError):
    """The GitHub connection is missing, expired, or does not match the request."""


class GitHubAPIError(RuntimeError):
    """GitHub rejected a request or could not be reached."""


@dataclass(frozen=True, slots=True)
class GitHubAccount:
    """A destination a repository can be created under.

    Attributes
    ----------
    login : str
        Account or organization name.
    type : str
        Either ``"User"`` or ``"Organization"``.
    account_id : int
        Numeric GitHub identifier, used to confirm a personal account really is
        the connected user's.
    """

    login: str
    type: str
    account_id: int


@dataclass(frozen=True, slots=True)
class GitHubConnection:
    """A verified, workspace-bound GitHub authorization.

    Attributes
    ----------
    workspace_id : str
        Workspace the connection was granted for.
    access_token : str
        OAuth token, held only for the lifetime of the request.
    user_id : int
        Numeric identifier of the authorizing user.
    user_login : str
        Login of the authorizing user.
    """

    workspace_id: str
    access_token: str
    user_id: int
    user_login: str


class GitHubOAuthService:
    """Drive the OAuth handshake and publish one generated repository."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        """Build the service.

        Parameters
        ----------
        settings : Settings
            Application configuration supplying credentials and API endpoints.
        client : httpx.AsyncClient, optional
            Shared HTTP client. Publishing uploads one blob per generated file,
            so reusing connections avoids a TLS handshake per file. A private
            client is created when none is supplied.
        """
        self.settings = settings
        self._fernet = (
            _fernet(settings.github_cookie_secret) if settings.github_cookie_secret else None
        )
        self._client = client or httpx.AsyncClient(timeout=30)
        self._owns_client = client is None

    async def close(self) -> None:
        """Close the HTTP client if this service created it."""
        if self._owns_client:
            await self._client.aclose()

    @property
    def configured(self) -> bool:
        """Whether the deployment can run the GitHub flow.

        Returns
        -------
        bool
            True when credentials and a public base URL are all present.
        """
        return self.settings.github_configured

    def begin_authorization(self, workspace_id: str, callback_url: str) -> tuple[str, str]:
        """Start the OAuth handshake.

        Parameters
        ----------
        workspace_id : str
            Workspace the resulting connection is bound to.
        callback_url : str
            Absolute callback URL, derived from configuration rather than from
            the request's ``Host`` header.

        Returns
        -------
        tuple of (str, str)
            The GitHub authorization URL and the encrypted state cookie value.
            The same value is used as the ``state`` parameter, so the callback
            can prove the browser that returns is the one that left.
        """
        self._require_configured()
        code_verifier = secrets.token_urlsafe(64)
        state_cookie = self._encrypt(
            {
                "purpose": "github-oauth-state",
                "workspace_id": workspace_id,
                "nonce": secrets.token_urlsafe(24),
                "code_verifier": code_verifier,
                "issued_at": int(time.time()),
            }
        )
        query = urlencode(
            {
                "client_id": self.settings.github_client_id,
                "redirect_uri": callback_url,
                "state": state_cookie,
                "scope": " ".join(GITHUB_OAUTH_SCOPES),
                "code_challenge": _base64url(hashlib.sha256(code_verifier.encode()).digest()),
                "code_challenge_method": "S256",
            }
        )
        return (
            f"{self.settings.github_web_url.rstrip('/')}/login/oauth/authorize?{query}",
            state_cookie,
        )

    async def complete_authorization(
        self,
        code: str,
        state: str,
        state_cookie: str | None,
        callback_url: str,
    ) -> tuple[str, str]:
        """Finish the OAuth handshake and mint a connection cookie.

        Parameters
        ----------
        code : str
            Temporary authorization code returned by GitHub.
        state : str
            State parameter returned by GitHub.
        state_cookie : str or None
            State cookie the browser sent back.
        callback_url : str
            The same callback URL used to start the handshake.

        Returns
        -------
        tuple of (str, str)
            Workspace identifier and the encrypted connection cookie value.

        Raises
        ------
        GitHubConnectionError
            If the state does not match, has expired, is malformed, or GitHub
            granted fewer scopes than the flow needs.
        """
        self._require_configured()
        # Compared as bytes: `compare_digest` refuses non-ASCII strings with a
        # TypeError, and `state` arrives from a query parameter, so comparing
        # them as text turns a malformed callback into a 500 instead of the
        # rejection it is.
        if not state_cookie or not secrets.compare_digest(state.encode(), state_cookie.encode()):
            raise GitHubConnectionError("GitHub authorization state did not match.")
        payload = self._decrypt(state)
        if payload.get("purpose") != "github-oauth-state":
            raise GitHubConnectionError("GitHub authorization state is invalid.")
        issued_at = payload.get("issued_at")
        if not isinstance(issued_at, int) or time.time() - issued_at > GITHUB_STATE_MAX_AGE_SECONDS:
            raise GitHubConnectionError("GitHub authorization expired; please connect again.")
        workspace_id = payload.get("workspace_id")
        if not isinstance(workspace_id, str):
            raise GitHubConnectionError("GitHub authorization state is invalid.")
        code_verifier = payload.get("code_verifier")
        if not isinstance(code_verifier, str) or not code_verifier:
            raise GitHubConnectionError("GitHub authorization state is invalid.")

        data = await self._exchange_code(code, callback_url, code_verifier)
        access_token = data.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise GitHubConnectionError("GitHub did not return an access token.")
        granted_scopes = {
            scope.strip() for scope in str(data.get("scope", "")).split(",") if scope.strip()
        }
        missing_scopes = set(GITHUB_OAUTH_SCOPES) - granted_scopes
        if missing_scopes:
            await self._revoke_token(access_token)
            raise GitHubConnectionError(
                "GitHub authorization did not grant the required scopes: "
                + ", ".join(sorted(missing_scopes))
                + "."
            )
        identity = await self._request(access_token, "GET", "/user")
        user_id = identity.get("id") if isinstance(identity, dict) else None
        user_login = identity.get("login") if isinstance(identity, dict) else None
        if not isinstance(user_id, int) or not isinstance(user_login, str):
            raise GitHubConnectionError("GitHub did not return a verified user identity.")
        connection_cookie = self._encrypt(
            {
                "purpose": "github-connection",
                "workspace_id": workspace_id,
                "access_token": access_token,
                "user_id": user_id,
                "user_login": user_login,
                "issued_at": int(time.time()),
            }
        )
        return workspace_id, connection_cookie

    def read_connection(self, cookie: str | None, workspace_id: str) -> GitHubConnection:
        """Decrypt and validate a connection cookie for one workspace.

        Parameters
        ----------
        cookie : str or None
            Cookie value sent by the browser.
        workspace_id : str
            Workspace the request is operating on.

        Returns
        -------
        GitHubConnection
            The verified connection.

        Raises
        ------
        GitHubConnectionError
            If the cookie is absent, undecryptable, expired, malformed, or was
            issued for a different workspace.
        """
        if not cookie:
            raise GitHubConnectionError("Connect GitHub before creating a repository.")
        payload = self._decrypt(cookie)
        if payload.get("purpose") != "github-connection":
            raise GitHubConnectionError("The GitHub connection is invalid.")
        issued_at = payload.get("issued_at")
        if (
            not isinstance(issued_at, int)
            or time.time() - issued_at > GITHUB_CONNECTION_MAX_AGE_SECONDS
        ):
            raise GitHubConnectionError("The GitHub connection expired; please connect again.")
        if payload.get("workspace_id") != workspace_id:
            raise GitHubConnectionError("The GitHub connection belongs to another workspace.")
        access_token = payload.get("access_token")
        user_id = payload.get("user_id")
        user_login = payload.get("user_login")
        if (
            not isinstance(access_token, str)
            or not access_token
            or not isinstance(user_id, int)
            or not isinstance(user_login, str)
        ):
            raise GitHubConnectionError("The GitHub connection is invalid.")
        return GitHubConnection(
            workspace_id=workspace_id,
            access_token=access_token,
            user_id=user_id,
            user_login=user_login,
        )

    async def list_accounts(self, connection: GitHubConnection) -> list[GitHubAccount]:
        """List the destinations this connection may create a repository under.

        Parameters
        ----------
        connection : GitHubConnection
            The verified connection.

        Returns
        -------
        list of GitHubAccount
            The authorizing user first, then their organizations.
        """
        accounts = [
            GitHubAccount(
                login=connection.user_login,
                type="User",
                account_id=connection.user_id,
            )
        ]
        organizations = await self._request(
            connection.access_token, "GET", "/user/orgs?per_page=100"
        )
        for organization in organizations if isinstance(organizations, list) else []:
            login = organization.get("login") if isinstance(organization, dict) else None
            account_id = organization.get("id") if isinstance(organization, dict) else None
            if isinstance(login, str) and isinstance(account_id, int):
                accounts.append(
                    GitHubAccount(login=login, type="Organization", account_id=account_id)
                )
        return accounts

    async def publish_repository(
        self,
        connection: GitHubConnection,
        account: GitHubAccount,
        repository: GeneratedRepository,
        name: str,
        private: bool,
        description: str,
        homepage: str | None = None,
        topics: tuple[str, ...] = (),
    ) -> str:
        """Create a repository and write the generated files as one initial commit.

        Parameters
        ----------
        connection : GitHubConnection
            The verified connection.
        account : GitHubAccount
            Destination account or organization.
        repository : GeneratedRepository
            The rendered file tree.
        name : str
            Repository name requested by the user.
        private : bool
            Whether the repository is created private.
        description : str
            Repository description.
        homepage : str or None
            Public website shown in the GitHub repository sidebar.
        topics : tuple of str
            Sanitized GitHub topics derived from RSM keywords.

        Returns
        -------
        str
            Web URL of the created repository.

        Raises
        ------
        GitHubConnectionError
            If the name is unsafe, the destination is not permitted, or the
            generated tree fails validation.
        GitHubAPIError
            If GitHub rejects a request or cannot be reached.
        """
        if not SAFE_GITHUB_NAME.fullmatch(name) or name in {".", ".."}:
            raise GitHubConnectionError(
                "Repository names may contain letters, numbers, dots, underscores, and hyphens."
            )
        validate_repository(repository)
        if account.type == "User" and account.account_id != connection.user_id:
            raise GitHubConnectionError(
                "A personal repository can only be created for the connected GitHub user."
            )
        if account.type not in {"User", "Organization"}:
            raise GitHubConnectionError("Choose a personal account or organization.")

        endpoint = "/user/repos" if account.type == "User" else f"/orgs/{account.login}/repos"
        # GitHub rejects Git database calls against an empty repository. Bootstrap
        # the Git database, then replace that branch with our parentless generated
        # commit so the visible history still contains one initial commit.
        created = await self._request(
            connection.access_token,
            "POST",
            endpoint,
            {
                "name": name,
                "private": private,
                "description": description,
                "homepage": homepage or "",
                "auto_init": True,
            },
        )
        owner = created.get("owner", {}).get("login")
        repo_name = created.get("name")
        html_url = created.get("html_url")
        default_branch = created.get("default_branch")
        if not all(isinstance(value, str) and value for value in (owner, repo_name, html_url)):
            raise GitHubAPIError(
                "GitHub created the repository but returned an incomplete response."
            )
        if topics:
            await self._request(
                connection.access_token,
                "PUT",
                f"/repos/{owner}/{repo_name}/topics",
                {"names": list(topics)},
            )
        tree_entries: list[dict[str, str]] = []
        for file in repository.files:
            blob = await self._request(
                connection.access_token,
                "POST",
                f"/repos/{owner}/{repo_name}/git/blobs",
                {
                    "content": base64.b64encode(file.content).decode(),
                    "encoding": "base64",
                },
            )
            tree_entries.append(
                {
                    "path": file.path,
                    "mode": "100755" if file.executable else "100644",
                    "type": "blob",
                    "sha": str(blob["sha"]),
                }
            )
        tree = await self._request(
            connection.access_token,
            "POST",
            f"/repos/{owner}/{repo_name}/git/trees",
            {"tree": tree_entries},
        )
        commit = await self._request(
            connection.access_token,
            "POST",
            f"/repos/{owner}/{repo_name}/git/commits",
            {
                "message": "Initial commit generated by LUMC Research Software Tools",
                "tree": tree["sha"],
            },
        )
        branch = default_branch if isinstance(default_branch, str) and default_branch else "main"
        await self._request(
            connection.access_token,
            "PATCH",
            f"/repos/{owner}/{repo_name}/git/refs/heads/{branch}",
            {
                "sha": commit["sha"],
                "force": True,
            },
        )
        return html_url

    async def revoke_authorization(self, connection: GitHubConnection) -> bool:
        """Revoke the user's OAuth grant, including all tokens issued to this app.

        Parameters
        ----------
        connection : GitHubConnection
            The connection to revoke.

        Returns
        -------
        bool
            True when GitHub confirmed the revocation.
        """
        return await self._revoke_token(connection.access_token)

    async def _revoke_token(self, access_token: str) -> bool:
        """Ask GitHub to delete the whole app authorization for this token."""
        self._require_configured()
        assert self.settings.github_client_id is not None
        assert self.settings.github_client_secret is not None
        try:
            response = await self._client.request(
                "DELETE",
                f"{self.settings.github_api_url.rstrip('/')}/applications/"
                f"{self.settings.github_client_id}/grant",
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": self.settings.github_api_version,
                },
                auth=(self.settings.github_client_id, self.settings.github_client_secret),
                json={"access_token": access_token},
            )
        except httpx.HTTPError:
            return False
        return response.status_code == 204

    async def _exchange_code(
        self, code: str, callback_url: str, code_verifier: str
    ) -> dict[str, Any]:
        """Trade the authorization code for an access token."""
        try:
            response = await self._client.post(
                f"{self.settings.github_web_url.rstrip('/')}/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": self.settings.github_client_id,
                    "client_secret": self.settings.github_client_secret,
                    "code": code,
                    "redirect_uri": callback_url,
                    "code_verifier": code_verifier,
                },
            )
        except httpx.HTTPError as exc:
            raise GitHubConnectionError(
                "Could not reach GitHub to complete authorization. Please try again."
            ) from exc
        data = _github_response(response, "GitHub authorization failed")
        if not isinstance(data, dict):
            raise GitHubConnectionError("GitHub returned an invalid authorization response.")
        return data

    async def _request(
        self,
        access_token: str,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> Any:
        """Call the GitHub REST API and translate failures into readable errors."""
        context = _github_request_context(method, path)
        try:
            response = await self._client.request(
                method,
                f"{self.settings.github_api_url.rstrip('/')}{path}",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {access_token}",
                    "X-GitHub-Api-Version": self.settings.github_api_version,
                },
                json=body,
            )
        except httpx.HTTPError as exc:
            raise GitHubAPIError(f"{context}: could not reach GitHub.") from exc
        return _github_response(response, context)

    def _encrypt(self, payload: dict[str, Any]) -> str:
        """Encrypt a cookie payload with the configured cookie secret."""
        self._require_configured()
        assert self._fernet is not None
        return self._fernet.encrypt(json.dumps(payload, separators=(",", ":")).encode()).decode()

    def _decrypt(self, token: str) -> dict[str, Any]:
        """Decrypt a cookie payload, rejecting anything tampered with."""
        self._require_configured()
        assert self._fernet is not None
        try:
            payload = json.loads(self._fernet.decrypt(token.encode()).decode())
        except (InvalidToken, ValueError, json.JSONDecodeError) as exc:
            raise GitHubConnectionError("The GitHub connection is invalid.") from exc
        if not isinstance(payload, dict):
            raise GitHubConnectionError("The GitHub connection is invalid.")
        return payload

    def _require_configured(self) -> None:
        """Fail clearly when the optional integration is not configured."""
        if not self.configured:
            raise GitHubNotConfiguredError(
                "GitHub publishing is not configured on this deployment."
            )


def _fernet(secret: str) -> Fernet:
    """Derive a Fernet key from the configured cookie secret."""
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def _base64url(value: bytes) -> str:
    """Encode bytes as unpadded base64url, as PKCE requires."""
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _github_request_context(method: str, path: str) -> str:
    """Describe what an API call was trying to do, for use in error messages."""
    if method == "GET" and path == "/user":
        return "GitHub could not read your user profile"
    if method == "GET" and path.startswith("/user/orgs"):
        return "GitHub could not list your organizations"
    if method == "POST" and (path == "/user/repos" or path.endswith("/repos")):
        return "GitHub could not create the repository"
    if path.endswith("/git/blobs"):
        return "GitHub could not upload the generated file data"
    if path.endswith("/git/trees"):
        return "GitHub could not assemble the generated file tree"
    if path.endswith("/git/commits"):
        return "GitHub could not create the generated commit"
    if "/git/refs/" in path:
        return "GitHub could not publish the generated branch"
    return "GitHub request failed"


def _github_response(response: httpx.Response, fallback: str) -> Any:
    """Return the decoded body, or raise with GitHub's own explanation.

    Parameters
    ----------
    response : httpx.Response
        The response to inspect.
    fallback : str
        Context describing what was being attempted.

    Returns
    -------
    Any
        The decoded JSON body on success.

    Raises
    ------
    GitHubAPIError
        On any non-success status, carrying GitHub's message and up to three of
        its field-level errors.
    """
    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.is_success:
        return data
    message = None
    if isinstance(data, dict):
        message = data.get("message") or data.get("error_description") or data.get("error")
    details: list[str] = []
    errors = data.get("errors", []) if isinstance(data, dict) else []
    for error in errors[:3] if isinstance(errors, list) else []:
        if isinstance(error, str):
            details.append(_short_error(error))
            continue
        if not isinstance(error, dict):
            continue
        detail = error.get("message")
        resource = error.get("resource")
        field = error.get("field")
        code = error.get("code")
        location = ".".join(
            value for value in (resource, field) if isinstance(value, str) and value
        )
        if isinstance(detail, str) and detail:
            rendered = detail
        elif isinstance(code, str) and code:
            rendered = code.replace("_", " ")
        else:
            continue
        details.append(_short_error(f"{rendered} ({location})" if location else rendered))
    summary = _short_error(message) if isinstance(message, str) and message else "Request failed"
    suffix = f" Details: {'; '.join(details)}." if details else ""
    raise GitHubAPIError(f"{fallback} (HTTP {response.status_code}): {summary}.{suffix}")


def _short_error(value: str) -> str:
    """Collapse whitespace and clip an upstream message to a readable length."""
    return " ".join(value.split())[:240].rstrip(".")

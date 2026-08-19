"""Runtime configuration sourced from environment variables.

Every setting is read once, at :class:`Settings` construction, from a
``RS_TOOLS_``-prefixed environment variable. The object is frozen so that a
request handler can never change deployment configuration at runtime, and it
carries no dependency on FastAPI, Redis, or the generators.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from rs_tools.generators.base import RepositoryTemplateSource

DEFAULT_REPOSITORY_TEMPLATE_URL = "https://github.com/LUMC-DCC/rs-repo-templates.git"
# Development default; use a version tag once template releases are available.
DEFAULT_REPOSITORY_TEMPLATE_REVISION = "main"


def _positive_int(name: str, default: int) -> int:
    """Read a strictly positive integer from the environment.

    Parameters
    ----------
    name : str
        Environment variable to read.
    default : int
        Value used when the variable is unset.

    Returns
    -------
    int
        The configured value.

    Raises
    ------
    ValueError
        If the variable is not an integer, or is not greater than zero.
    """
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _csv_tuple(name: str, default: str = "") -> tuple[str, ...]:
    """Read a comma-separated list, dropping empty entries.

    Parameters
    ----------
    name : str
        Environment variable to read.
    default : str, optional
        Comma-separated value used when the variable is unset.

    Returns
    -------
    tuple of str
        The configured entries, stripped of surrounding whitespace.
    """
    return tuple(value.strip() for value in os.getenv(name, default).split(",") if value.strip())


def _default_frontend_dist() -> Path:
    """Return the built frontend directory used when running from a source checkout.

    Returns
    -------
    pathlib.Path
        ``frontend/dist`` relative to the repository root.
    """
    return Path(__file__).resolve().parents[3] / "frontend" / "dist"


def _public_base_url(name: str) -> str | None:
    """Read and validate the public origin the service is reached on.

    Parameters
    ----------
    name : str
        Environment variable to read.

    Returns
    -------
    str or None
        The origin without a trailing slash, or ``None`` when unset.

    Raises
    ------
    ValueError
        If the value is not an absolute ``http``/``https`` URL.
    """
    value = os.getenv(name, "").strip()
    if not value:
        return None
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError(f"{name} must be an absolute http(s) URL, for example https://example.org")
    return value.rstrip("/")


def _secret_value(name: str) -> str | None:
    r"""Read a secret from an environment variable or its Docker/Kubernetes secret file.

    Parameters
    ----------
    name : str
        Environment variable holding the secret inline. The same name suffixed
        with ``_FILE`` is read as a path instead.

    Returns
    -------
    str or None
        The secret, or ``None`` when neither variable is set.

    Raises
    ------
    ValueError
        If both the inline value and the file are set, or the file is unreadable.
    """
    inline_value = os.getenv(name)
    file_name = os.getenv(f"{name}_FILE")
    if inline_value and file_name:
        raise ValueError(f"Set either {name} or {name}_FILE, not both")

    value = inline_value
    if file_name:
        try:
            value = Path(file_name).read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"Could not read {name}_FILE: {exc}") from exc

    if not value:
        return None
    return value.strip()


@dataclass(frozen=True, slots=True)
class Settings:
    """Complete application configuration, read from the environment.

    Attributes are populated from ``RS_TOOLS_``-prefixed environment variables.
    Construct with explicit keyword arguments in tests to bypass the environment
    entirely.
    """

    redis_url: str = field(
        default_factory=lambda: os.getenv("RS_TOOLS_REDIS_URL", "redis://localhost:6379/0"),
        metadata={"description": "Redis connection URL for temporary workspace state."},
    )
    workspace_ttl_seconds: int = field(
        default_factory=lambda: _positive_int("RS_TOOLS_WORKSPACE_TTL_SECONDS", 12 * 60 * 60),
        metadata={"description": "Workspace inactivity lifetime, in seconds."},
    )
    max_request_bytes: int = field(
        default_factory=lambda: _positive_int("RS_TOOLS_MAX_REQUEST_BYTES", 1_048_576),
        metadata={"description": "Maximum accepted HTTP request body, in bytes."},
    )
    public_base_url: str | None = field(
        default_factory=lambda: _public_base_url("RS_TOOLS_PUBLIC_BASE_URL"),
        metadata={"description": "Public HTTP(S) origin used in generated URLs and OAuth."},
    )
    frontend_dist: Path = field(
        default_factory=lambda: Path(
            os.getenv("RS_TOOLS_FRONTEND_DIST", str(_default_frontend_dist()))
        ),
        metadata={
            "description": "Directory containing the compiled frontend.",
            "documented_default": "frontend/dist",
        },
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("RS_TOOLS_LOG_LEVEL", "INFO").strip().upper(),
        metadata={"description": "Python logging level."},
    )
    # Empty by default: the Vite development server proxies /api to this
    # application, so the browser only ever sees one origin and no cross-origin
    # request is made. Set this only when a separate origin really calls the API.
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: _csv_tuple("RS_TOOLS_CORS_ORIGINS"),
        metadata={"description": "Comma-separated browser origins allowed to call the API."},
    )
    # Host header allow-list. The default accepts anything, which is correct for
    # local development; a public deployment should name its own hostnames so a
    # forged Host header cannot reach the application at all.
    trusted_hosts: tuple[str, ...] = field(
        default_factory=lambda: _csv_tuple("RS_TOOLS_TRUSTED_HOSTS", "*"),
        metadata={"description": "Comma-separated Host header allow-list."},
    )
    rate_limit_requests: int = field(
        default_factory=lambda: _positive_int("RS_TOOLS_RATE_LIMIT_REQUESTS", 120),
        metadata={"description": "Ordinary requests allowed per client and rate-limit window."},
    )
    rate_limit_heavy_requests: int = field(
        default_factory=lambda: _positive_int("RS_TOOLS_RATE_LIMIT_HEAVY_REQUESTS", 10),
        metadata={"description": "Expensive requests allowed per client and window."},
    )
    rate_limit_window_seconds: int = field(
        default_factory=lambda: _positive_int("RS_TOOLS_RATE_LIMIT_WINDOW_SECONDS", 60),
        metadata={"description": "Rate-limit window length, in seconds."},
    )
    repository_template_url: str = field(
        default_factory=lambda: os.getenv(
            "RS_TOOLS_REPOSITORY_TEMPLATE_URL", DEFAULT_REPOSITORY_TEMPLATE_URL
        ),
        metadata={"description": "Trusted Copier repository used for project scaffolds."},
    )
    repository_template_revision: str = field(
        default_factory=lambda: os.getenv(
            "RS_TOOLS_REPOSITORY_TEMPLATE_REVISION", DEFAULT_REPOSITORY_TEMPLATE_REVISION
        ),
        metadata={"description": "Git branch, tag, or commit of the Copier repository."},
    )
    github_client_id: str | None = field(
        default_factory=lambda: os.getenv("RS_TOOLS_GITHUB_CLIENT_ID") or None,
        metadata={"description": "Client ID of the optional GitHub OAuth App."},
    )
    github_client_secret: str | None = field(
        default_factory=lambda: _secret_value("RS_TOOLS_GITHUB_CLIENT_SECRET"),
        metadata={
            "description": "Client secret of the GitHub OAuth App.",
            "file_variant": True,
        },
    )
    github_cookie_secret: str | None = field(
        default_factory=lambda: _secret_value("RS_TOOLS_GITHUB_COOKIE_SECRET"),
        metadata={
            "description": "Secret used to encrypt temporary GitHub connection cookies.",
            "file_variant": True,
        },
    )
    github_api_url: str = field(
        default_factory=lambda: os.getenv("RS_TOOLS_GITHUB_API_URL", "https://api.github.com"),
        metadata={"description": "GitHub REST API base URL."},
    )
    github_web_url: str = field(
        default_factory=lambda: os.getenv("RS_TOOLS_GITHUB_WEB_URL", "https://github.com"),
        metadata={"description": "GitHub web and OAuth base URL."},
    )
    github_api_version: str = field(
        default_factory=lambda: os.getenv("RS_TOOLS_GITHUB_API_VERSION", "2026-03-10"),
        metadata={"description": "GitHub REST API version header."},
    )

    @property
    def github_configured(self) -> bool:
        """Whether the optional GitHub publishing flow can run.

        ``public_base_url`` is required alongside the credentials: the OAuth
        callback URL is built from it, and deriving that from the request's
        ``Host`` header would let a forged header choose where the authorization
        code is sent.

        Returns
        -------
        bool
            True when every value the OAuth flow needs is configured.
        """
        return bool(
            self.github_client_id
            and self.github_client_secret
            and self.github_cookie_secret
            and self.public_base_url
        )

    @property
    def repository_template_source(self) -> RepositoryTemplateSource:
        """Return the configured Copier template source.

        Returns
        -------
        RepositoryTemplateSource
            Repository URL and configured revision.
        """
        return RepositoryTemplateSource(
            url=self.repository_template_url,
            revision=self.repository_template_revision,
        )

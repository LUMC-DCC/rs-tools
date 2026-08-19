"""FastAPI dependency accessors and shared route parameter types.

Services are built once in the application factory and stored on
``app.state``. These accessors are the only place route modules reach for them,
so a route never constructs a service and tests can override one in place.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Path, Request

from rs_tools.config import Settings
from rs_tools.github import GitHubOAuthService
from rs_tools.rate_limit import BUCKET_DEFAULT, BUCKET_HEAVY, RateLimiter, client_identity
from rs_tools.services import WorkspaceService


def get_workspace_service(request: Request) -> WorkspaceService:
    """Return the shared workspace service.

    Parameters
    ----------
    request : fastapi.Request
        The incoming request.

    Returns
    -------
    WorkspaceService
        The service built by the application factory.
    """
    return request.app.state.workspace_service


def get_settings(request: Request) -> Settings:
    """Return the frozen application settings.

    Parameters
    ----------
    request : fastapi.Request
        The incoming request.

    Returns
    -------
    Settings
        The settings built by the application factory.
    """
    return request.app.state.settings


def get_github_service(request: Request) -> GitHubOAuthService:
    """Return the shared GitHub OAuth service.

    Parameters
    ----------
    request : fastapi.Request
        The incoming request.

    Returns
    -------
    GitHubOAuthService
        The service built by the application factory.
    """
    return request.app.state.github_service


def get_rate_limiter(request: Request) -> RateLimiter:
    """Return the shared rate limiter.

    Parameters
    ----------
    request : fastapi.Request
        The incoming request.

    Returns
    -------
    RateLimiter
        The limiter built by the application factory.
    """
    return request.app.state.rate_limiter


async def enforce_default_rate_limit(request: Request) -> None:
    """Count one ordinary request against the caller's budget.

    Parameters
    ----------
    request : fastapi.Request
        The incoming request.

    Raises
    ------
    RateLimitExceeded
        If the caller has exhausted the window's budget.
    """
    settings: Settings = request.app.state.settings
    limiter: RateLimiter = request.app.state.rate_limiter
    await limiter.check(
        bucket=BUCKET_DEFAULT,
        identity=client_identity(request),
        limit=settings.rate_limit_requests,
    )


async def enforce_heavy_rate_limit(request: Request) -> None:
    """Count one expensive request against the caller's smaller budget.

    Applied to the operations that render templates, clone a repository, or call
    GitHub, all of which cost far more than a workspace read.

    Parameters
    ----------
    request : fastapi.Request
        The incoming request.

    Raises
    ------
    RateLimitExceeded
        If the caller has exhausted the window's budget.
    """
    settings: Settings = request.app.state.settings
    limiter: RateLimiter = request.app.state.rate_limiter
    await limiter.check(
        bucket=BUCKET_HEAVY,
        identity=client_identity(request),
        limit=settings.rate_limit_heavy_requests,
    )


WorkspaceServiceDependency = Annotated[WorkspaceService, Depends(get_workspace_service)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
GitHubServiceDependency = Annotated[GitHubOAuthService, Depends(get_github_service)]

#: Workspace identifiers are always server-generated UUID4 values. Constraining
#: the path parameter keeps arbitrary client input out of storage keys entirely.
WorkspaceId = Annotated[
    str,
    Path(
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        description="Workspace identifier.",
    ),
]

"""Absolute URLs the application hands out.

Both helpers prefer configured values over anything derived from the request.
``Host`` and ``X-Forwarded-Host`` are client-controlled, so building a callback
or a shareable link from them would let a forged header choose where a user, or
an OAuth authorization code, is sent.
"""

from __future__ import annotations

from fastapi import Request

from rs_tools.config import Settings


def base_url(request: Request, settings: Settings) -> str:
    """Return the origin the service is reachable on, without a trailing slash.

    Parameters
    ----------
    request : fastapi.Request
        Used only as a development fallback when no public base URL is set.
    settings : Settings
        Application settings.

    Returns
    -------
    str
        The configured public origin, or the request's own origin.
    """
    configured = settings.public_base_url
    return (configured or str(request.base_url)).rstrip("/")


def workspace_url(request: Request, settings: Settings, workspace_id: str) -> str:
    """Return the browser page for one workspace.

    Parameters
    ----------
    request : fastapi.Request
        Used only as a development fallback.
    settings : Settings
        Application settings.
    workspace_id : str
        Workspace identifier.

    Returns
    -------
    str
        Absolute URL of the workspace editor.
    """
    return f"{base_url(request, settings)}/w/{workspace_id}"


def github_callback_url(settings: Settings) -> str:
    """Return the OAuth callback URL registered with the GitHub App.

    Deliberately takes no request: the callback must match what is registered
    with GitHub exactly, and must never be influenced by request headers.

    Parameters
    ----------
    settings : Settings
        Application settings. ``public_base_url`` is required, which
        ``Settings.github_configured`` already enforces.

    Returns
    -------
    str
        Absolute callback URL.
    """
    assert settings.public_base_url is not None
    return f"{settings.public_base_url.rstrip('/')}/api/github/callback"

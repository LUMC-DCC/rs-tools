"""The optional GitHub connection and repository publishing flow.

The access token never reaches Redis or workspace data. It lives only inside an
encrypted, HttpOnly cookie that is bound to one workspace, and the service
attempts to revoke the whole OAuth grant after publishing succeeds.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from rs_tools.api.dependencies import (
    GitHubServiceDependency,
    SettingsDependency,
    WorkspaceId,
    WorkspaceServiceDependency,
    enforce_default_rate_limit,
    enforce_heavy_rate_limit,
)
from rs_tools.api.urls import github_callback_url, workspace_url
from rs_tools.generators import GeneratorOptions, render_repository
from rs_tools.github import (
    GITHUB_CONNECTION_COOKIE,
    GITHUB_CONNECTION_MAX_AGE_SECONDS,
    GITHUB_STATE_COOKIE,
    GITHUB_STATE_MAX_AGE_SECONDS,
    GitHubConnectionError,
    enrich_repository_urls,
    repository_metadata,
)
from rs_tools.models import GitHubRepositoryRequest

router = APIRouter(tags=["github"])


@router.get(
    "/workspaces/{workspace_id}/github",
    response_model=None,
    dependencies=[Depends(enforce_default_rate_limit)],
)
async def github_connection_status(
    workspace_id: WorkspaceId,
    request: Request,
    service: WorkspaceServiceDependency,
    github: GitHubServiceDependency,
) -> dict[str, Any]:
    """Report whether this workspace currently has a usable GitHub connection.

    An unusable cookie is reported as "not connected" rather than as an error:
    from the user's point of view an expired connection and no connection call
    for exactly the same next step.

    Parameters
    ----------
    workspace_id : str
        Workspace identifier.
    request : fastapi.Request
        Carries the connection cookie.
    service : WorkspaceService
        Injected workspace service, used to confirm the workspace still exists.
    github : GitHubOAuthService
        Injected GitHub service.

    Returns
    -------
    dict
        Whether the integration is configured and connected, and the accounts
        available as publishing destinations.
    """
    await service.get(workspace_id)
    result: dict[str, Any] = {"configured": github.configured, "connected": False, "accounts": []}
    if not github.configured:
        return result
    cookie = request.cookies.get(GITHUB_CONNECTION_COOKIE)
    if not cookie:
        return result
    try:
        connection = github.read_connection(cookie, workspace_id)
    except GitHubConnectionError:
        return result
    accounts = await github.list_accounts(connection)
    result["connected"] = True
    result["accounts"] = [{"login": account.login, "type": account.type} for account in accounts]
    return result


@router.post(
    "/workspaces/{workspace_id}/github/connect",
    response_model=None,
    dependencies=[Depends(enforce_heavy_rate_limit)],
)
async def connect_github(
    workspace_id: WorkspaceId,
    response: Response,
    service: WorkspaceServiceDependency,
    settings: SettingsDependency,
    github: GitHubServiceDependency,
) -> dict[str, str]:
    """Begin the OAuth handshake for one workspace.

    Parameters
    ----------
    workspace_id : str
        Workspace identifier.
    response : fastapi.Response
        Used to set the short-lived state cookie.
    service : WorkspaceService
        Injected workspace service, used to confirm the workspace still exists.
    settings : Settings
        Injected application settings.
    github : GitHubOAuthService
        Injected GitHub service.

    Returns
    -------
    dict of str to str
        The GitHub authorization URL the browser should be sent to.
    """
    await service.get(workspace_id)
    callback_url = github_callback_url(settings)
    authorization_url, state_cookie = github.begin_authorization(workspace_id, callback_url)
    response.set_cookie(
        GITHUB_STATE_COOKIE,
        state_cookie,
        max_age=GITHUB_STATE_MAX_AGE_SECONDS,
        httponly=True,
        secure=callback_url.startswith("https://"),
        samesite="lax",
        path="/api/github",
    )
    return {"authorization_url": authorization_url}


@router.get(
    "/github/callback",
    response_model=None,
    dependencies=[Depends(enforce_heavy_rate_limit)],
)
async def github_callback(
    request: Request,
    settings: SettingsDependency,
    service: WorkspaceServiceDependency,
    github: GitHubServiceDependency,
    code: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
    state: Annotated[str | None, Query(min_length=1, max_length=4096)] = None,
    error: Annotated[str | None, Query(max_length=256)] = None,
) -> RedirectResponse:
    """Complete the OAuth handshake and return the user to their workspace.

    Parameters
    ----------
    request : fastapi.Request
        Carries the state cookie.
    settings : Settings
        Injected application settings.
    service : WorkspaceService
        Injected workspace service, used to confirm the workspace still exists.
    github : GitHubOAuthService
        Injected GitHub service.
    code : str, optional
        Temporary authorization code from GitHub.
    state : str, optional
        State parameter from GitHub.
    error : str, optional
        Error slug when the user declined or GitHub refused.

    Returns
    -------
    fastapi.responses.RedirectResponse
        A redirect back to the workspace page, carrying the connection cookie.

    Raises
    ------
    GitHubConnectionError
        If GitHub reported an error or returned an incomplete response.
    """
    if error:
        raise GitHubConnectionError(f"GitHub authorization was not completed: {error}.")
    if not code or not state:
        raise GitHubConnectionError("GitHub authorization returned an incomplete response.")
    callback_url = github_callback_url(settings)
    workspace_id, connection_cookie = await github.complete_authorization(
        code,
        state,
        request.cookies.get(GITHUB_STATE_COOKIE),
        callback_url,
    )
    await service.get(workspace_id)
    response = RedirectResponse(
        f"{workspace_url(request, settings, workspace_id)}?github=connected",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.delete_cookie(GITHUB_STATE_COOKIE, path="/api/github")
    response.set_cookie(
        GITHUB_CONNECTION_COOKIE,
        connection_cookie,
        max_age=GITHUB_CONNECTION_MAX_AGE_SECONDS,
        httponly=True,
        secure=callback_url.startswith("https://"),
        samesite="lax",
        path="/api",
    )
    return response


@router.delete(
    "/workspaces/{workspace_id}/github",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(enforce_default_rate_limit)],
)
async def disconnect_github(
    workspace_id: WorkspaceId,
    request: Request,
    response: Response,
    service: WorkspaceServiceDependency,
    github: GitHubServiceDependency,
) -> None:
    """Revoke the OAuth grant and drop the connection cookie.

    A cookie that cannot be read is not an error here: the user asked to be
    disconnected, and clearing the cookie achieves that either way.

    Parameters
    ----------
    workspace_id : str
        Workspace identifier.
    request : fastapi.Request
        Carries the connection cookie.
    response : fastapi.Response
        Used to clear the connection cookie.
    service : WorkspaceService
        Injected workspace service, used to confirm the workspace still exists.
    github : GitHubOAuthService
        Injected GitHub service.
    """
    await service.get(workspace_id)
    try:
        connection = github.read_connection(
            request.cookies.get(GITHUB_CONNECTION_COOKIE), workspace_id
        )
        await github.revoke_authorization(connection)
    except GitHubConnectionError:
        pass
    response.delete_cookie(GITHUB_CONNECTION_COOKIE, path="/api")


@router.post(
    "/workspaces/{workspace_id}/github/repositories",
    response_model=None,
    dependencies=[Depends(enforce_heavy_rate_limit)],
)
async def publish_github_repository(
    workspace_id: WorkspaceId,
    options: GitHubRepositoryRequest,
    request: Request,
    response: Response,
    service: WorkspaceServiceDependency,
    settings: SettingsDependency,
    github: GitHubServiceDependency,
) -> dict[str, str | bool]:
    """Generate a repository and publish it under the chosen account.

    The requested owner is matched against the accounts GitHub reports for this
    connection, so a client cannot name an arbitrary organization.

    Parameters
    ----------
    workspace_id : str
        Workspace identifier.
    options : GitHubRepositoryRequest
        Destination, name, visibility, and template.
    request : fastapi.Request
        Carries the connection cookie.
    response : fastapi.Response
        Used to clear the connection cookie after revocation.
    service : WorkspaceService
        Injected workspace service.
    settings : Settings
        Injected application settings, supplying the template source.
    github : GitHubOAuthService
        Injected GitHub service.

    Returns
    -------
    dict
        The created repository URL, and whether the grant was revoked. When
        revocation fails the repository still exists, so the caller is told
        rather than left to assume access is gone.

    Raises
    ------
    GitHubConnectionError
        If the chosen owner is not a destination this connection may use.
    """
    workspace = await service.get(workspace_id)
    connection = github.read_connection(
        request.cookies.get(GITHUB_CONNECTION_COOKIE),
        workspace_id,
    )
    accounts = await github.list_accounts(connection)
    account = next(
        (
            candidate
            for candidate in accounts
            if candidate.login.casefold() == options.owner.casefold()
        ),
        None,
    )
    if account is None:
        raise GitHubConnectionError("Choose your GitHub account or one of your organizations.")
    enriched_data = enrich_repository_urls(
        workspace.data,
        account.login,
        options.name,
        options.template,
    )
    repository = await run_in_threadpool(
        render_repository,
        enriched_data,
        GeneratorOptions(
            template_id=options.template,
            repository_template_source=settings.repository_template_source,
        ),
    )
    metadata = repository_metadata(enriched_data)
    url = await github.publish_repository(
        connection,
        account,
        repository,
        options.name,
        options.private,
        metadata.description,
        metadata.homepage,
        metadata.topics,
    )
    authorization_revoked = await github.revoke_authorization(connection)
    if authorization_revoked:
        response.delete_cookie(GITHUB_CONNECTION_COOKIE, path="/api")
    return {"url": url, "authorization_revoked": authorization_revoked}

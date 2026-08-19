"""Create, read, replace, and download workspace documents."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status

from rs_tools.api.dependencies import (
    SettingsDependency,
    WorkspaceId,
    WorkspaceServiceDependency,
    enforce_default_rate_limit,
)
from rs_tools.api.urls import workspace_url
from rs_tools.models import Workspace

router = APIRouter(
    prefix="/workspaces",
    tags=["workspaces"],
    dependencies=[Depends(enforce_default_rate_limit)],
)


@router.post("", response_model=Workspace, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    data: dict[str, Any],
    request: Request,
    response: Response,
    service: WorkspaceServiceDependency,
    settings: SettingsDependency,
) -> Workspace:
    """Validate an RSM document and store it in a new workspace.

    Parameters
    ----------
    data : dict
        The complete RSM document.
    request : fastapi.Request
        Used to derive the browser destination when no public base URL is set.
    response : fastapi.Response
        Used to set the ``Location`` header.
    service : WorkspaceService
        Injected workspace service.
    settings : Settings
        Injected application settings.

    Returns
    -------
    Workspace
        The created workspace. ``Location`` carries the page a browser should
        open, so any API client can hand a user straight to the editor.
    """
    workspace = await service.create(data)
    response.headers["Location"] = workspace_url(request, settings, workspace.id)
    return workspace


@router.post("/empty", response_model=Workspace, status_code=status.HTTP_201_CREATED)
async def create_empty_workspace(
    request: Request,
    response: Response,
    service: WorkspaceServiceDependency,
    settings: SettingsDependency,
) -> Workspace:
    """Create a workspace holding the smallest valid RSM document.

    Parameters
    ----------
    request : fastapi.Request
        Used to derive the browser destination when no public base URL is set.
    response : fastapi.Response
        Used to set the ``Location`` header.
    service : WorkspaceService
        Injected workspace service.
    settings : Settings
        Injected application settings.

    Returns
    -------
    Workspace
        The created workspace.
    """
    workspace = await service.create_empty()
    response.headers["Location"] = workspace_url(request, settings, workspace.id)
    return workspace


@router.get("/{workspace_id}", response_model=Workspace)
async def get_workspace(
    workspace_id: WorkspaceId,
    service: WorkspaceServiceDependency,
) -> Workspace:
    """Retrieve a workspace and restart its expiry clock.

    Parameters
    ----------
    workspace_id : str
        Workspace identifier.
    service : WorkspaceService
        Injected workspace service.

    Returns
    -------
    Workspace
        The stored workspace.
    """
    return await service.get(workspace_id)


@router.put("/{workspace_id}", response_model=Workspace)
async def replace_workspace_data(
    workspace_id: WorkspaceId,
    data: dict[str, Any],
    service: WorkspaceServiceDependency,
) -> Workspace:
    """Replace the complete RSM document and refresh the workspace TTL.

    ``PUT`` rather than ``PATCH``: the body is always the whole replacement
    document, which keeps update and validation semantics unambiguous.

    Parameters
    ----------
    workspace_id : str
        Workspace identifier.
    data : dict
        Complete replacement RSM document.
    service : WorkspaceService
        Injected workspace service.

    Returns
    -------
    Workspace
        The updated workspace.
    """
    return await service.replace_data(workspace_id, data)


@router.get("/{workspace_id}/download")
async def download_workspace(
    workspace_id: WorkspaceId,
    service: WorkspaceServiceDependency,
) -> Response:
    """Download the stored RSM document as a JSON file.

    Parameters
    ----------
    workspace_id : str
        Workspace identifier.
    service : WorkspaceService
        Injected workspace service.

    Returns
    -------
    fastapi.Response
        A ``rsm.json`` attachment. The filename is fixed, never client-supplied.
    """
    workspace = await service.get(workspace_id)
    return Response(
        content=json.dumps(workspace.data, indent=2, ensure_ascii=False) + "\n",
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="rsm.json"'},
    )

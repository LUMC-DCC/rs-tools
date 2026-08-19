"""Download generated files and repository scaffolds.

One route serves the whole catalogue. Adding a generator to the registry
publishes it here without a new endpoint, and clients discover it through
``GET /api/generators``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from starlette.concurrency import run_in_threadpool

from rs_tools.api.dependencies import (
    SettingsDependency,
    WorkspaceId,
    WorkspaceServiceDependency,
    enforce_heavy_rate_limit,
)
from rs_tools.generators import GeneratorOptions, get_generator

router = APIRouter(
    prefix="/workspaces",
    tags=["generators"],
    dependencies=[Depends(enforce_heavy_rate_limit)],
)


@router.get("/{workspace_id}/generators/{generator_id}")
async def generated_file(
    workspace_id: WorkspaceId,
    generator_id: str,
    service: WorkspaceServiceDependency,
    settings: SettingsDependency,
    template: str | None = Query(
        default=None,
        max_length=64,
        description="Repository template identifier; ignored by file generators.",
    ),
) -> Response:
    """Generate any registered file through one consistent endpoint.

    Rendering is CPU-bound and, for repositories, does network work, so it runs
    in a worker thread rather than blocking the event loop.

    Parameters
    ----------
    workspace_id : str
        Workspace identifier.
    generator_id : str
        Identifier from ``GET /api/generators``.
    service : WorkspaceService
        Injected workspace service.
    settings : Settings
        Injected application settings, supplying the template source.
    template : str, optional
        Repository template to render.

    Returns
    -------
    fastapi.Response
        The generated file as an attachment.

    Raises
    ------
    fastapi.HTTPException
        With status 404 when no generator has that identifier.
    """
    try:
        generator = get_generator(generator_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Generator not found.") from exc

    workspace = await service.get(workspace_id)
    options = GeneratorOptions(
        template_id=template,
        repository_template_source=settings.repository_template_source,
    )
    artifact = await run_in_threadpool(generator.generate, workspace.data, options)
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.filename}"'},
    )

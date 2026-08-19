"""Liveness and readiness for orchestrators and uptime checks."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from rs_tools.api.dependencies import WorkspaceServiceDependency

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(service: WorkspaceServiceDependency) -> dict[str, str]:
    """Report whether the application and its storage are usable.

    Redis holds all workspace state, so an application that cannot reach it is
    not ready to serve traffic even though its own process is healthy.

    Parameters
    ----------
    service : WorkspaceService
        Injected workspace service, used to reach the store.

    Returns
    -------
    dict of str to str
        ``{"status": "ok"}`` when storage responded.

    Raises
    ------
    fastapi.HTTPException
        With status 503 when storage is unreachable.
    """
    try:
        await service.store.ping()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage is unavailable.",
        ) from exc
    return {"status": "ok"}

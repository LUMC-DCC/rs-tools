"""HTTP routes, grouped by concern.

Each module owns one area of the API and mounts under the shared ``/api``
prefix. Assembling them here keeps the application factory free of route detail
and makes the surface of the API readable in one place.
"""

from fastapi import APIRouter

from rs_tools.api.routes import artifacts, catalogue, github, health, workspaces

router = APIRouter(prefix="/api")
router.include_router(health.router)
router.include_router(catalogue.router)
router.include_router(workspaces.router)
router.include_router(artifacts.router)
router.include_router(github.router)

__all__ = ["router"]

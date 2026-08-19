"""FastAPI application factory and production entry point.

Everything the application needs is built here and stored on ``app.state``, so
route modules never construct a service and a test can substitute one by passing
it to :func:`create_app`.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from rs_tools import __version__
from rs_tools.api.routes import router
from rs_tools.config import Settings
from rs_tools.generators import GeneratorInputError, GeneratorUnavailable, build_catalogue
from rs_tools.github import (
    GitHubAPIError,
    GitHubConnectionError,
    GitHubNotConfiguredError,
    GitHubOAuthService,
)
from rs_tools.middleware import RequestSizeLimitMiddleware, SecurityHeadersMiddleware
from rs_tools.rate_limit import RateLimiter, RateLimitExceeded
from rs_tools.schema.service import RSMValidationError, SchemaService
from rs_tools.services import WorkspaceNotFoundError, WorkspaceService
from rs_tools.storage.base import WorkspaceStore
from rs_tools.storage.redis import RedisWorkspaceStore

logger = logging.getLogger(__name__)


def _encode(document: object) -> bytes:
    """Serialize a document that never changes, once.

    Parameters
    ----------
    document : object
        A JSON-serializable structure.

    Returns
    -------
    bytes
        The encoded JSON body, ready to return verbatim.
    """
    return json.dumps(document, ensure_ascii=False).encode("utf-8")


def create_app(*, settings: Settings | None = None, store: WorkspaceStore | None = None) -> FastAPI:
    """Build the application.

    Parameters
    ----------
    settings : Settings, optional
        Configuration to use. Read from the environment when omitted.
    store : WorkspaceStore, optional
        Storage backend. A Redis store is created, and owned, when omitted.

    Returns
    -------
    fastapi.FastAPI
        The configured application.
    """
    app_settings = settings or Settings()
    logging.basicConfig(
        level=app_settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    owns_store = store is None
    workspace_store = store or RedisWorkspaceStore.from_url(
        app_settings.redis_url, app_settings.workspace_ttl_seconds
    )
    schema_service = SchemaService()
    service = WorkspaceService(workspace_store, schema_service)
    github_service = GitHubOAuthService(app_settings)
    rate_limiter = RateLimiter(workspace_store, app_settings.rate_limit_window_seconds)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if not app_settings.github_configured:
            logger.info("GitHub publishing is disabled; credentials are not configured")
        yield
        await github_service.close()
        if owns_store:
            await workspace_store.close()

    application = FastAPI(
        title="Research Software Tools API",
        version=__version__,
        summary="Turn Research Software Management metadata into reusable software artifacts.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        # FastAPI otherwise publishes a Swagger OAuth2 redirect helper at
        # /docs/oauth2-redirect, outside the /api namespace. Nothing here uses
        # an OAuth2 flow in the API docs, so it is surface for no purpose.
        swagger_ui_oauth2_redirect_url=None,
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.state.workspace_service = service
    application.state.github_service = github_service
    application.state.rate_limiter = rate_limiter
    # The schema and the generator catalogue are byte-identical for every
    # caller, and producing them costs real work: resolving the catalogue walks
    # the schema repeatedly, and both are large to serialize. Built and encoded
    # once here, so an unauthenticated client cannot spend the service's CPU
    # just by asking for them repeatedly.
    application.state.generator_catalogue = _encode(build_catalogue(schema_service))
    application.state.schema_document = _encode(schema_service.schema)

    _add_middleware(application, app_settings)
    _add_exception_handlers(application)
    application.include_router(router)
    _add_frontend_routes(application, app_settings.frontend_dist)
    return application


def _add_middleware(application: FastAPI, settings: Settings) -> None:
    """Install the middleware stack.

    Starlette runs the most recently added middleware first, so these are added
    inside-out. The resulting order, outermost first, is:

    1. security headers, so every response carries them, including the ones the
       middleware below generate;
    2. the host check, so a forged ``Host`` never reaches a handler;
    3. CORS, so its headers appear on rejections as well as on successes;
    4. the body limit, closest to the application it protects.

    Parameters
    ----------
    application : fastapi.FastAPI
        The application being built.
    settings : Settings
        Application settings.
    """
    application.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.max_request_bytes)
    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Content-Type"],
        )
    # "*" means every host is accepted, which is the default and is only right
    # for local development; installing the middleware then would reject nothing
    # while still inspecting every request.
    if settings.trusted_hosts and set(settings.trusted_hosts) != {"*"}:
        application.add_middleware(
            TrustedHostMiddleware, allowed_hosts=list(settings.trusted_hosts)
        )
    application.add_middleware(
        SecurityHeadersMiddleware,
        hsts=bool(settings.public_base_url and settings.public_base_url.startswith("https://")),
    )


def _add_exception_handlers(application: FastAPI) -> None:
    """Translate domain errors into responses that are safe to show a user.

    Every handler returns a message written for the person using the service. An
    unexpected exception is left to FastAPI, which returns a generic 500 without
    leaking a traceback.

    Parameters
    ----------
    application : fastapi.FastAPI
        The application being built.
    """

    @application.exception_handler(RSMValidationError)
    async def validation_error_handler(_: Request, exc: RSMValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": str(exc),
                "errors": [issue.model_dump() for issue in exc.issues],
            },
        )

    @application.exception_handler(WorkspaceNotFoundError)
    async def workspace_not_found_handler(_: Request, __: WorkspaceNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": "Workspace not found or expired."},
        )

    @application.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": str(exc)},
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    @application.exception_handler(GeneratorInputError)
    async def generator_input_error_handler(_: Request, exc: GeneratorInputError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @application.exception_handler(GeneratorUnavailable)
    async def generator_unavailable_handler(_: Request, exc: GeneratorUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @application.exception_handler(GitHubNotConfiguredError)
    async def github_not_configured_handler(
        _: Request, exc: GitHubNotConfiguredError
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @application.exception_handler(GitHubConnectionError)
    async def github_connection_error_handler(
        _: Request, exc: GitHubConnectionError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @application.exception_handler(GitHubAPIError)
    async def github_api_error_handler(_: Request, exc: GitHubAPIError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})


def _add_frontend_routes(application: FastAPI, dist: Path) -> None:
    """Serve the built single-page application, or a hint that it is missing.

    Parameters
    ----------
    application : fastapi.FastAPI
        The application being built.
    dist : pathlib.Path
        Directory holding the compiled frontend.
    """
    index = dist / "index.html"
    assets = dist / "assets"
    if assets.is_dir():
        application.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

    def frontend_response() -> FileResponse | HTMLResponse:
        if index.is_file():
            return FileResponse(index)
        return HTMLResponse(
            """
            <!doctype html><html>
            <body style="font-family:system-ui;max-width:42rem;margin:4rem auto">
            <h1>Research Software Tools</h1>
            <p>The API is running. Start the frontend development server at
            <code>http://localhost:5173</code>, or build <code>frontend/dist</code>.</p>
            <p><a href="/api/docs">Open API documentation</a></p>
            </body></html>
            """,
            status_code=503,
        )

    @application.api_route(
        "/", methods=["GET", "HEAD"], include_in_schema=False, response_model=None
    )
    async def homepage() -> FileResponse | HTMLResponse:
        return frontend_response()

    @application.api_route(
        "/{path:path}", methods=["GET", "HEAD"], include_in_schema=False, response_model=None
    )
    async def spa_fallback(path: str) -> FileResponse | HTMLResponse | JSONResponse:
        # Client-side routes are served the same document; unmatched API paths
        # must stay JSON 404s so a mistyped endpoint does not return HTML.
        if path == "api" or path.startswith("api/"):
            return JSONResponse({"detail": "Not found."}, status_code=404)
        return frontend_response()


app = create_app()

"""ASGI middleware used for public deployment safety."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Every directive names this origin and nothing else: the interface loads no
# third-party script, style, font, or image, so a visitor's browser contacts no
# host but this one. The typefaces are bundled rather than fetched from a font
# CDN precisely so this stays true. Styles are inlined by the Vite build, which
# is why 'unsafe-inline' is required for style-src and not for script-src.
CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "base-uri 'self'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "object-src 'none'",
        "img-src 'self' data:",
        "style-src 'self' 'unsafe-inline'",
        "script-src 'self'",
        "connect-src 'self'",
        "font-src 'self'",
    )
)

SECURITY_HEADERS: tuple[tuple[str, str], ...] = (
    ("Content-Security-Policy", CONTENT_SECURITY_POLICY),
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "no-referrer"),
    ("Cross-Origin-Opener-Policy", "same-origin"),
    ("Permissions-Policy", "geolocation=(), camera=(), microphone=(), payment=()"),
)


class SecurityHeadersMiddleware:
    """Attach a restrictive set of response headers to every response.

    These belong in the application rather than only in a reverse proxy so that
    the guarantees hold wherever the container runs, including behind a proxy
    nobody has configured yet.
    """

    def __init__(self, app: ASGIApp, *, hsts: bool = False) -> None:
        """Wrap an ASGI application.

        Parameters
        ----------
        app : ASGIApp
            The application to wrap.
        hsts : bool, optional
            Whether to send ``Strict-Transport-Security``. Enabled only when the
            public base URL is HTTPS, since sending it over plain HTTP would pin
            a browser to a scheme the deployment does not serve.
        """
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass the request through and decorate the response start message."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS:
                    headers.setdefault(name, value)
                if self.hsts:
                    headers.setdefault(
                        "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
                    )
            await send(message)

        await self.app(scope, receive, send_with_headers)


class RequestSizeLimitMiddleware:
    """Reject request bodies above a configured byte limit, including chunked bodies.

    ``Content-Length`` alone is not enough: a chunked request declares no length,
    so the body is also counted as it arrives and the request is cut off as soon
    as it passes the limit.
    """

    def __init__(self, app: Callable[..., Awaitable[None]], max_bytes: int) -> None:
        """Wrap an ASGI application.

        Parameters
        ----------
        app : ASGIApp
            The application to wrap.
        max_bytes : int
            Largest accepted request body.
        """
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Buffer and measure the request body before handing it on."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_bytes:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                await self._reject(scope, receive, send, "Invalid Content-Length header.")
                return

        messages: list[Message] = []
        total = 0
        more_body = True
        while more_body:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request":
                break
            total += len(message.get("body", b""))
            if total > self.max_bytes:
                await self._reject(scope, receive, send)
                return
            more_body = message.get("more_body", False)

        async def replay() -> Message:
            if messages:
                return messages.pop(0)
            return {"type": "http.disconnect"}

        await self.app(scope, replay, send)

    async def _reject(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        detail: str = "Request body is too large.",
    ) -> None:
        """Answer with 413 without reading the rest of the body."""
        response = JSONResponse({"detail": detail}, status_code=413)
        await response(scope, receive, send)

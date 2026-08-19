"""Per-client request limits for a public, unauthenticated service.

Every workspace is anonymous, so the only thing between the service and a
scripted client is a limit on how often one address may call the expensive
operations. Counters live in the workspace store with a native expiry, which
keeps them correct across several application processes and needs no cleanup
task.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import Request

from rs_tools.storage.base import WorkspaceStore

logger = logging.getLogger(__name__)

KEY_PREFIX = "rs-tools:rate:"

#: Budget for ordinary reads and edits.
BUCKET_DEFAULT = "default"
#: Budget for operations that render templates, clone a repository, or call
#: GitHub. These are orders of magnitude more expensive than a workspace read.
BUCKET_HEAVY = "heavy"


class RateLimitExceeded(Exception):
    """A client exceeded its request budget for the current window.

    Attributes
    ----------
    retry_after_seconds : int
        How long the client should wait before retrying.
    """

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Too many requests. Please wait a moment and try again.")
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class RateLimiter:
    """Fixed-window request counter.

    A fixed window is used rather than a sliding one because the goal is to stop
    one client monopolizing the service, not to meter usage precisely. It costs
    one round trip and keeps no background state.

    Attributes
    ----------
    store : WorkspaceStore
        Backend holding the counters.
    window_seconds : int
        Length of the counting window.
    """

    store: WorkspaceStore
    window_seconds: int

    async def check(self, *, bucket: str, identity: str, limit: int) -> None:
        """Count one request and reject it when the bucket is exhausted.

        A storage failure is logged and allowed through. Losing rate limiting is
        a better outcome than refusing every request because the counter store is
        briefly unavailable, and any operation that needs a workspace fails on
        its own in that situation.

        Parameters
        ----------
        bucket : str
            Name of the budget, so cheap and expensive operations count apart.
        identity : str
            Client identifier, normally the remote address.
        limit : int
            Requests permitted per window.

        Raises
        ------
        RateLimitExceeded
            If this client already used its budget for the current window.
        """
        key = f"{KEY_PREFIX}{bucket}:{identity}"
        try:
            count = await self.store.increment_with_expiry(key, self.window_seconds)
        except Exception:
            logger.warning("Rate limiting unavailable; allowing request", exc_info=True)
            return
        if count > limit:
            raise RateLimitExceeded(self.window_seconds)


def client_identity(request: Request) -> str:
    """Return the identity a request is rate limited under.

    Uvicorn rewrites the client address from ``X-Forwarded-For`` when started
    with ``--proxy-headers``, so behind a trusted proxy this is the real caller.
    The header is never read directly here: doing so would let any client choose
    its own identity and bypass the limit.

    Parameters
    ----------
    request : fastapi.Request
        The incoming request.

    Returns
    -------
    str
        The remote address, or ``"unknown"`` when the transport has none.
    """
    return request.client.host if request.client else "unknown"

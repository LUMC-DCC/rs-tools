"""Storage boundaries used by the application services.

Both protocols are structural, so the workspace service and the rate limiter can
be exercised against any conforming implementation without a Redis server.
"""

from __future__ import annotations

from typing import Protocol

from rs_tools.models import Workspace


class WorkspaceStore(Protocol):
    """Temporary storage for workspace documents."""

    async def create(self, workspace: Workspace) -> bool:
        """Store a new workspace, failing if the identifier is already taken.

        Parameters
        ----------
        workspace : Workspace
            The workspace to store.

        Returns
        -------
        bool
            True when the workspace was stored, False on an identifier collision.
        """
        ...

    async def get(self, workspace_id: str, *, refresh_ttl: bool = True) -> Workspace | None:
        """Load a workspace, optionally extending its lifetime.

        Parameters
        ----------
        workspace_id : str
            Identifier to load.
        refresh_ttl : bool, optional
            Whether reading counts as activity and restarts the expiry clock.

        Returns
        -------
        Workspace or None
            The workspace, or None when it does not exist or has expired.
        """
        ...

    async def replace(self, workspace: Workspace) -> bool:
        """Replace an existing workspace and restart its expiry clock.

        Parameters
        ----------
        workspace : Workspace
            The replacement, carrying an existing identifier.

        Returns
        -------
        bool
            True when replaced, False when the workspace expired meanwhile.
        """
        ...

    async def increment_with_expiry(self, key: str, ttl_seconds: int) -> int:
        """Increment a counter, setting its expiry only when it is first created.

        Parameters
        ----------
        key : str
            Counter key.
        ttl_seconds : int
            Lifetime applied when the counter is created.

        Returns
        -------
        int
            The counter value after incrementing.
        """
        ...

    async def ping(self) -> bool:
        """Check that the storage backend is reachable.

        Returns
        -------
        bool
            True when the backend responded.
        """
        ...

    async def close(self) -> None:
        """Release the connection held by this store."""
        ...

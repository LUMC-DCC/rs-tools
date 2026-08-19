"""Redis implementation of temporary workspace storage.

Redis owns workspace lifetime through its own key expiry, so the application
carries no cleanup worker and can restart without losing active workspaces.
"""

from __future__ import annotations

from redis.asyncio import Redis
from redis.exceptions import WatchError

from rs_tools.models import Workspace


class RedisWorkspaceStore:
    """Store each workspace as a single JSON value with a Redis-native TTL."""

    key_prefix = "rs-tools:workspace:"

    def __init__(self, client: Redis, ttl_seconds: int) -> None:
        """Wrap an existing Redis client.

        Parameters
        ----------
        client : redis.asyncio.Redis
            Connected client, configured to decode responses.
        ttl_seconds : int
            Inactivity lifetime applied to every workspace key.
        """
        self._client = client
        self._ttl_seconds = ttl_seconds

    @classmethod
    def from_url(cls, url: str, ttl_seconds: int) -> RedisWorkspaceStore:
        """Build a store from a Redis connection URL.

        Parameters
        ----------
        url : str
            Redis connection URL.
        ttl_seconds : int
            Inactivity lifetime applied to every workspace key.

        Returns
        -------
        RedisWorkspaceStore
            A store owning its own client.
        """
        client = Redis.from_url(url, decode_responses=True)
        return cls(client, ttl_seconds)

    def key_for(self, workspace_id: str) -> str:
        """Return the Redis key holding one workspace.

        Parameters
        ----------
        workspace_id : str
            Workspace identifier.

        Returns
        -------
        str
            The namespaced key.
        """
        return f"{self.key_prefix}{workspace_id}"

    async def create(self, workspace: Workspace) -> bool:
        """Store a new workspace, failing if the identifier is already taken.

        Parameters
        ----------
        workspace : Workspace
            The workspace to store.

        Returns
        -------
        bool
            True when stored, False when the key already existed.
        """
        result = await self._client.set(
            self.key_for(workspace.id),
            workspace.model_dump_json(),
            ex=self._ttl_seconds,
            nx=True,
        )
        return bool(result)

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
        key = self.key_for(workspace_id)
        if refresh_ttl:
            raw = await self._client.getex(key, ex=self._ttl_seconds)
        else:
            raw = await self._client.get(key)
        return Workspace.model_validate_json(raw) if raw is not None else None

    async def replace(self, workspace: Workspace) -> bool:
        """Replace an existing workspace and restart its expiry clock.

        The write is guarded by ``WATCH`` so a workspace that expires between the
        existence check and the write is not silently recreated past its TTL.

        Parameters
        ----------
        workspace : Workspace
            The replacement, carrying an existing identifier.

        Returns
        -------
        bool
            True when replaced, False when the workspace expired meanwhile.
        """
        key = self.key_for(workspace.id)
        async with self._client.pipeline(transaction=True) as pipeline:
            while True:
                try:
                    await pipeline.watch(key)
                    if not await pipeline.exists(key):
                        await pipeline.reset()
                        return False
                    pipeline.multi()
                    pipeline.set(
                        key,
                        workspace.model_dump_json(),
                        ex=self._ttl_seconds,
                    )
                    await pipeline.execute()
                    return True
                except WatchError:
                    continue

    async def increment_with_expiry(self, key: str, ttl_seconds: int) -> int:
        """Increment a counter, setting its expiry only when it is first created.

        ``NX`` on the expiry is what makes the window fixed: later increments in
        the same window must not push the reset further out, or a client sending
        a steady stream would never see the counter reset.

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
        async with self._client.pipeline(transaction=True) as pipeline:
            pipeline.incr(key)
            pipeline.expire(key, ttl_seconds, nx=True)
            count, _ = await pipeline.execute()
        return int(count)

    async def ping(self) -> bool:
        """Check that Redis is reachable.

        Returns
        -------
        bool
            True when Redis responded.
        """
        return bool(await self._client.ping())

    async def close(self) -> None:
        """Close the underlying Redis connection."""
        await self._client.aclose()

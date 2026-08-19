"""Application-level workspace operations.

This is the only place that combines schema validation with storage. Route
handlers stay thin, and the same operations are usable from tests or a
command-line tool without an HTTP layer.
"""

from __future__ import annotations

from uuid import uuid4

from rs_tools.models import Workspace, utc_now
from rs_tools.schema.service import SchemaService
from rs_tools.storage.base import WorkspaceStore


class WorkspaceNotFoundError(LookupError):
    """The requested workspace does not exist or has expired."""


class WorkspaceService:
    """Create, read, and replace validated workspace documents."""

    def __init__(self, store: WorkspaceStore, schema: SchemaService) -> None:
        """Build the service.

        Parameters
        ----------
        store : WorkspaceStore
            Temporary storage backend.
        schema : SchemaService
            Validator and defaults source for the RSM contract.
        """
        self.store = store
        self.schema = schema

    async def create(self, data: object) -> Workspace:
        """Validate a document and store it under a fresh identifier.

        Parameters
        ----------
        data : object
            Candidate RSM document.

        Returns
        -------
        Workspace
            The stored workspace.

        Raises
        ------
        RSMValidationError
            If the document does not conform to the RSM schema.
        RuntimeError
            If three consecutive identifiers collided, which indicates a broken
            random source rather than bad luck.
        """
        validated = self.schema.validate(data)
        for _ in range(3):
            workspace = Workspace(id=str(uuid4()), data=validated)
            if await self.store.create(workspace):
                return workspace
        raise RuntimeError("Could not allocate a unique workspace identifier")

    async def create_empty(self) -> Workspace:
        """Create a workspace holding the smallest valid RSM document.

        Returns
        -------
        Workspace
            The stored workspace.
        """
        return await self.create(self.schema.empty_document())

    async def get(self, workspace_id: str) -> Workspace:
        """Load a workspace, treating the read as activity.

        Parameters
        ----------
        workspace_id : str
            Identifier to load.

        Returns
        -------
        Workspace
            The stored workspace, with its expiry clock restarted.

        Raises
        ------
        WorkspaceNotFoundError
            If the workspace does not exist or has expired.
        """
        workspace = await self.store.get(workspace_id, refresh_ttl=True)
        if workspace is None:
            raise WorkspaceNotFoundError(workspace_id)
        return workspace

    async def replace_data(self, workspace_id: str, data: object) -> Workspace:
        """Validate a document and replace a workspace's contents with it.

        Replacement rather than patching keeps update and validation semantics
        unambiguous: the body is always the complete document, and identity and
        timestamps stay server-owned.

        Parameters
        ----------
        workspace_id : str
            Identifier to update.
        data : object
            Complete replacement RSM document.

        Returns
        -------
        Workspace
            The updated workspace.

        Raises
        ------
        RSMValidationError
            If the document does not conform to the RSM schema.
        WorkspaceNotFoundError
            If the workspace does not exist or expired during the update.
        """
        validated = self.schema.validate(data)
        existing = await self.store.get(workspace_id, refresh_ttl=False)
        if existing is None:
            raise WorkspaceNotFoundError(workspace_id)
        updated = existing.model_copy(update={"data": validated, "updated_at": utc_now()})
        if not await self.store.replace(updated):
            raise WorkspaceNotFoundError(workspace_id)
        return updated

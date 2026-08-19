"""Application data models.

These describe the application's own envelope around an RSM document. The RSM
document itself is never modelled here: the published JSON Schema is the single
contract, so a parallel Pydantic copy of it could only drift.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC value.

    Returns
    -------
    datetime.datetime
        The current UTC time.
    """
    return datetime.now(UTC)


class Workspace(BaseModel):
    """Complete ephemeral workspace representation, stored as one Redis value.

    Attributes
    ----------
    id : str
        UUID4 identifier, also the unguessable part of the workspace URL.
    data : dict
        The RSM document, validated against the published schema before storage.
    created_at : datetime.datetime
        When the workspace was created.
    updated_at : datetime.datetime
        When the document was last replaced.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    data: dict[str, Any]
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ValidationIssue(BaseModel):
    """Frontend-friendly JSON Schema validation error.

    Attributes
    ----------
    path : str
        JSON Pointer to the offending value, or ``"$"`` for the document root.
        The interface uses it to focus the matching form control.
    message : str
        The validator's explanation, safe to show to a user.
    validator : str or None
        Name of the JSON Schema keyword that failed.
    """

    path: str
    message: str
    validator: str | None = None


class GitHubRepositoryRequest(BaseModel):
    """Options chosen immediately before publishing generated files to GitHub.

    Attributes
    ----------
    owner : str
        Destination account or organization login.
    name : str
        Repository name. Constrained here as well as in the service, so an
        invalid name is rejected before any GitHub call is made.
    private : bool
        Whether the repository is created private. Deliberately has no default:
        visibility is not something to get by omission, so a caller that does
        not say is asked rather than guessed for.
    template : str or None
        Identifier of the repository template to render.
    """

    model_config = ConfigDict(extra="forbid")

    owner: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    private: bool
    template: str | None = None

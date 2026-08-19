"""Types shared by generator implementations.

Nothing here imports FastAPI, Redis, or the workspace service. A generator is a
plain function from an RSM document to a :class:`GeneratedArtifact`, which keeps
the catalogue usable from tests and command-line tooling as well as from HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass


class GeneratorInputError(ValueError):
    """The generator cannot run with the requested document or options."""


class GeneratorUnavailable(RuntimeError):
    """The generator itself is misconfigured or its source cannot be reached.

    Distinct from :class:`GeneratorInputError` because nothing the person using
    the service can change will fix it.
    """


@dataclass(frozen=True, slots=True)
class GeneratedArtifact:
    """One rendered file, ready to be returned as an HTTP response body.

    Attributes
    ----------
    filename : str
        Name offered to the client. Always fixed or sanitized by the generator;
        it is never taken from user input.
    media_type : str
        Content type of :attr:`content`.
    content : bytes
        The rendered file.
    """

    filename: str
    media_type: str
    content: bytes


@dataclass(frozen=True, slots=True)
class RepositoryTemplateSource:
    """Where Copier repository templates are fetched from.

    Attributes
    ----------
    url : str
        Copier template source, as a Git URL or local path.
    revision : str
        Git branch, tag, or commit to render. Prefer a version tag for deployed
        releases when one is available.
    """

    url: str
    revision: str


@dataclass(frozen=True, slots=True)
class GeneratorOptions:
    """Per-request choices passed to every generator.

    File generators ignore these; the repository generator uses them to select
    a language template and to locate its Copier source.

    Attributes
    ----------
    template_id : str or None
        Identifier of the chosen repository template, or ``None`` for the first
        registered one.
    repository_template_source : RepositoryTemplateSource or None
        Configured Copier source. ``None`` selects the built-in default.
    """

    template_id: str | None = None
    repository_template_source: RepositoryTemplateSource | None = None

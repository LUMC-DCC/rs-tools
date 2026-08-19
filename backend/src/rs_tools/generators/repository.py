"""Generate repository files from configurable Copier templates.

Rendering is deliberately the same for both consumers: the ZIP download and the
GitHub publisher share :func:`render_repository` and therefore share the safety
checks in :func:`validate_repository`.
"""

from __future__ import annotations

import io
import logging
import re
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path, PurePosixPath
from typing import Any

from copier import run_copy
from copier.errors import CopierError, TaskError
from jinja2 import TemplateError
from plumbum.commands.processes import CommandNotFound, ProcessExecutionError

from rs_tools.generators.base import (
    GeneratedArtifact,
    GeneratorInputError,
    GeneratorOptions,
    GeneratorUnavailable,
    RepositoryTemplateSource,
)
from rs_tools.schema.service import SchemaService

logger = logging.getLogger(__name__)

MAX_REPOSITORY_FILES = 1_000
MAX_REPOSITORY_BYTES = 20 * 1024 * 1024
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_PATH_LENGTH = 240

# Copier refreshes one cached Git mirror before creating a temporary worktree.
# Requests render in a thread pool, so serialize that shared cache operation
# inside this process.
_render_lock = threading.Lock()


@dataclass(frozen=True, slots=True)
class RepositoryTemplate:
    """One selectable language scaffold exposed by the Copier source.

    Attributes
    ----------
    id : str
        Stable identifier used by the API and the template selector.
    label : str
        Human-readable name shown in the interface.
    """

    id: str
    label: str

    def as_public_metadata(self) -> dict[str, str]:
        """Return the fields exposed through the public API.

        Returns
        -------
        dict of str to str
            Identifier and label.
        """
        return {"id": self.id, "label": self.label}


# Add another language template here; the API and the frontend selector both
# read this tuple, so no other file needs to change.
REPOSITORY_TEMPLATES: tuple[RepositoryTemplate, ...] = (
    RepositoryTemplate(id="generic", label="Generic"),
    RepositoryTemplate(id="python", label="Python"),
    RepositoryTemplate(id="r", label="R"),
)


@dataclass(frozen=True, slots=True)
class RepositoryFile:
    """One file in a generated repository.

    Attributes
    ----------
    path : str
        POSIX-style path relative to the repository root.
    content : bytes
        File contents.
    executable : bool
        Whether the file carries the executable bit.
    """

    path: str
    content: bytes
    executable: bool = False


@dataclass(frozen=True, slots=True)
class GeneratedRepository:
    """A rendered repository that has passed :func:`validate_repository`.

    Attributes
    ----------
    name : str
        Sanitized project directory name.
    files : tuple of RepositoryFile
        Every file below the project root, in sorted order.
    """

    name: str
    files: tuple[RepositoryFile, ...]


def generate_repository(
    smp: dict[str, Any],
    options: GeneratorOptions | None = None,
) -> GeneratedArtifact:
    """Render a repository and pack it into a ZIP archive.

    Parameters
    ----------
    smp : dict
        The complete RSM document, passed to Copier as answer data.
    options : GeneratorOptions, optional
        Template selection and source configuration.

    Returns
    -------
    GeneratedArtifact
        A ``.zip`` archive named after the generated project.

    Raises
    ------
    GeneratorInputError
        If the template is unknown or the rendered output is unsafe or empty.
    """
    repository = render_repository(smp, options)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in repository.files:
            info = zipfile.ZipInfo(f"{repository.name}/{file.path}")
            info.external_attr = (0o755 if file.executable else 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, file.content)

    return GeneratedArtifact(
        filename=f"{repository.name}.zip",
        media_type="application/zip",
        content=buffer.getvalue(),
    )


def render_repository(
    smp: dict[str, Any],
    options: GeneratorOptions | None = None,
) -> GeneratedRepository:
    """Render the selected template into a validated in-memory file tree.

    Parameters
    ----------
    smp : dict
        The complete RSM document, passed to Copier as answer data.
    options : GeneratorOptions, optional
        Template selection and source configuration.

    Returns
    -------
    GeneratedRepository
        The rendered files, already checked against the repository limits.

    Raises
    ------
    GeneratorInputError
        If the template is unknown, rejected the metadata, produced no files, or
        produced output that fails :func:`validate_repository`.
    GeneratorUnavailable
        If the configured template source could not be fetched.
    """
    resolved = options or GeneratorOptions()
    template = get_repository_template(resolved.template_id)
    source = resolved.repository_template_source or default_repository_template_source()

    with _render_lock:
        repository = _render(smp, template, source)
    validate_repository(repository)
    return repository


def default_repository_template_source() -> RepositoryTemplateSource:
    """Return the built-in template source used when nothing is configured.

    Imported lazily so that :mod:`rs_tools.config` can depend on the generator
    types without the generators depending on application configuration.

    Returns
    -------
    RepositoryTemplateSource
        The default LUMC-DCC Copier repository and revision.
    """
    from rs_tools.config import (
        DEFAULT_REPOSITORY_TEMPLATE_REVISION,
        DEFAULT_REPOSITORY_TEMPLATE_URL,
    )

    return RepositoryTemplateSource(
        url=DEFAULT_REPOSITORY_TEMPLATE_URL,
        revision=DEFAULT_REPOSITORY_TEMPLATE_REVISION,
    )


def get_repository_template(template_id: str | None) -> RepositoryTemplate:
    """Look up a registered repository template.

    Parameters
    ----------
    template_id : str or None
        Requested identifier. ``None`` selects the first registered template.

    Returns
    -------
    RepositoryTemplate
        The matching template.

    Raises
    ------
    GeneratorInputError
        If no registered template has that identifier.
    """
    selected = template_id or REPOSITORY_TEMPLATES[0].id
    for template in REPOSITORY_TEMPLATES:
        if template.id == selected:
            return template
    supported = ", ".join(template.id for template in REPOSITORY_TEMPLATES)
    raise GeneratorInputError(f"Unsupported repository template {selected!r}; choose {supported}.")


def validate_repository(repository: GeneratedRepository) -> None:
    """Reject generated output that is unsafe to archive or publish.

    Applied to every rendered repository, so a template change cannot introduce
    a traversal path, an oversized archive, or a committed secret through either
    the download or the GitHub route.

    Parameters
    ----------
    repository : GeneratedRepository
        The rendered file tree to check.

    Raises
    ------
    GeneratorInputError
        If the tree exceeds the size limits, contains an unsafe or colliding
        path, or contains a file that looks like a credential.
    """
    if len(repository.files) > MAX_REPOSITORY_FILES:
        raise GeneratorInputError("The generated repository contains too many files.")
    if sum(len(file.content) for file in repository.files) > MAX_REPOSITORY_BYTES:
        raise GeneratorInputError("The generated repository is too large.")

    normalized_paths: set[str] = set()
    for file in repository.files:
        path = PurePosixPath(file.path)
        normalized_path = str(path)
        if (
            path.is_absolute()
            or not path.parts
            or ".." in path.parts
            or path.parts[0] == ".git"
            or "\\" in file.path
            or "\0" in file.path
            or normalized_path == "."
            or len(file.path) > MAX_PATH_LENGTH
        ):
            raise GeneratorInputError("The generated repository contains an unsafe path.")
        if normalized_path in normalized_paths:
            raise GeneratorInputError(
                "The generated repository contains paths that collide after normalization."
            )
        normalized_paths.add(normalized_path)
        if len(file.content) > MAX_FILE_BYTES:
            raise GeneratorInputError(f"Generated file {file.path!r} is too large.")
        if _looks_like_a_secret(path.name, file.content):
            raise GeneratorInputError(
                f"Generation stopped because generated file {file.path!r} may contain a secret."
            )


SENSITIVE_FILENAMES = frozenset({".env", "id_rsa", "id_ed25519"})
SAFE_ENV_EXAMPLES = frozenset({".env.example", ".env.sample", ".env.template"})
SECRET_PATTERNS: tuple[re.Pattern[bytes], ...] = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"\bgh[opurs]_[A-Za-z0-9_]{30,}\b"),
    re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
)


def _looks_like_a_secret(filename: str, content: bytes) -> bool:
    """Report whether a generated file resembles credential material.

    Parameters
    ----------
    filename : str
        Base name of the generated file.
    content : bytes
        File contents.

    Returns
    -------
    bool
        True when the name or contents match a known credential shape.
    """
    name = filename.casefold()
    if name in SENSITIVE_FILENAMES or (name.startswith(".env.") and name not in SAFE_ENV_EXAMPLES):
        return True
    return any(pattern.search(content) for pattern in SECRET_PATTERNS)


def _render(
    smp: dict[str, Any],
    template: RepositoryTemplate,
    source: RepositoryTemplateSource,
) -> GeneratedRepository:
    """Run Copier and read the result into memory.

    Parameters
    ----------
    smp : dict
        RSM document used as Copier answer data.
    template : RepositoryTemplate
        Selected language template.
    source : RepositoryTemplateSource
        Copier repository and configured revision.

    Returns
    -------
    GeneratedRepository
        The rendered, not-yet-validated file tree.

    Raises
    ------
    GeneratorInputError
        If the template produced no files.
    """
    with tempfile.TemporaryDirectory(prefix="rs-tools-repository-") as temporary_directory:
        root = Path(temporary_directory)
        project_directory = root / "output"
        try:
            run_copy(
                source.url,
                project_directory,
                data=_copier_answers(smp, template.id),
                vcs_ref=source.revision,
                defaults=True,
                overwrite=False,
                quiet=True,
                unsafe=True,
            )
        except (CommandNotFound, ProcessExecutionError) as exc:
            # The template source is deployment configuration, not something the
            # person using the service chose, so this is not their mistake.
            logger.error("Repository template %r is unavailable", source.url, exc_info=True)
            raise GeneratorUnavailable(
                "The repository template could not be fetched. This is a problem with the "
                "deployment, not with your metadata."
            ) from exc
        except TaskError as exc:
            # The trusted template validates the complete normalized metadata in
            # a finalization task. Its detailed output is logged; do not guess
            # that every task failure is a project-slug problem.
            logger.warning(
                "Template %r rejected the metadata for %r",
                template.id,
                smp.get("project_slug"),
                exc_info=True,
            )
            raise GeneratorInputError(
                f"The {template.label} template rejected this metadata. Review the selected "
                "options and language-specific constraints, then try again."
            ) from exc
        except ValueError as exc:
            if str(exc).startswith("Validation error for question"):
                logger.warning(
                    "Template %r rejected the metadata for %r",
                    template.id,
                    smp.get("project_slug"),
                    exc_info=True,
                )
                raise GeneratorInputError(
                    f"The {template.label} template could not build a repository from this "
                    "metadata. Check that project_slug is a valid name for that language, then "
                    "try again."
                ) from exc
            logger.error("Repository template %r could not be rendered", source.url, exc_info=True)
            raise GeneratorUnavailable(
                "The repository template could not be rendered. This is a problem with the "
                "deployment, not with your metadata."
            ) from exc
        except (CopierError, TemplateError) as exc:
            logger.error("Repository template %r could not be rendered", source.url, exc_info=True)
            raise GeneratorUnavailable(
                "The repository template could not be rendered. This is a problem with the "
                "deployment, not with your metadata."
            ) from exc

        files = tuple(_collect_repository_files(project_directory))
        if not files:
            raise GeneratorInputError("The selected template generated no repository files.")
        return GeneratedRepository(
            name=_safe_name(str(smp.get("project_slug") or "")),
            files=files,
        )


@cache
def _rsm_schema() -> SchemaService:
    """Load the packaged schema once for Copier answer normalization."""
    return SchemaService()


def _copier_answers(smp: dict[str, Any], template_id: str) -> dict[str, Any]:
    """Complete supplied RSM objects without overriding Copier top-level defaults."""
    return {
        **_rsm_schema().complete_present_objects(smp),
        "template_type": template_id,
    }


def _collect_repository_files(project_directory: Path) -> list[RepositoryFile]:
    """Read every regular file below the generated project root.

    Symbolic links and anything under ``.git`` are skipped, so a template cannot
    smuggle a link out of the generated tree.

    Parameters
    ----------
    project_directory : pathlib.Path
        Root of the rendered project.

    Returns
    -------
    list of RepositoryFile
        Collected files, sorted by path.
    """
    files: list[RepositoryFile] = []
    for path in sorted(project_directory.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = PurePosixPath(path.relative_to(project_directory).as_posix())
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] == ".git":
            continue
        files.append(
            RepositoryFile(
                path=str(relative),
                content=path.read_bytes(),
                executable=bool(path.stat().st_mode & 0o111),
            )
        )
    return files


def _safe_name(value: str) -> str:
    """Reduce a generated directory name to a safe archive and repository name.

    Parameters
    ----------
    value : str
        Project slug used for the generated repository.

    Returns
    -------
    str
        A name limited to letters, digits, dots, underscores, and hyphens.
    """
    safe = "".join(character for character in value if character.isalnum() or character in "._-")
    safe = safe.strip(".-")[:100]
    return safe or "research-software"

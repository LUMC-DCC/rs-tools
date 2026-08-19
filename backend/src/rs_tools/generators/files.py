"""Adapters for the framework-independent ``rs-files-templates`` package.

The published package owns the file contract; this module adapts one of its
Pydantic models into an rs-tools generator and walks that contract so the
interface can show its inputs without a second, hand-maintained list.
"""

from __future__ import annotations

import inspect
import tempfile
from collections.abc import Callable
from pathlib import Path
from types import UnionType
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel, RootModel, ValidationError
from rs_files_templates import FileTemplateModel, render_file

from rs_tools.generators.base import GeneratedArtifact, GeneratorInputError, GeneratorOptions


def generator_for(
    model_type: type[FileTemplateModel],
) -> Callable[[dict[str, Any], GeneratorOptions], GeneratedArtifact]:
    """Create an rs-tools generator backed by one published file model.

    Parameters
    ----------
    model_type : type of FileTemplateModel
        Published model describing one output file.

    Returns
    -------
    callable
        ``generate(rsm, options) -> GeneratedArtifact``. ``options`` is accepted
        for signature parity with the repository generator and is unused here.
    """

    def generate(rsm: dict[str, Any], options: GeneratorOptions | None = None) -> GeneratedArtifact:
        del options
        payload = {name: rsm[name] for name in model_type.model_fields if name in rsm}
        try:
            model = model_type.model_validate(payload)
            with tempfile.TemporaryDirectory(prefix="rs-tools-file-") as directory:
                generated = render_file(model, directory)
                content = generated.path.read_bytes()
        except (ValidationError, ValueError) as exc:
            raise GeneratorInputError(
                f"The RSM metadata is not sufficient to generate {model_type.output_name}: {exc}"
            ) from exc
        return GeneratedArtifact(
            filename=Path(model_type.output_name).name,
            media_type=_media_type(model_type.media_type),
            content=content,
        )

    generate.__name__ = f"generate_{model_type.output_name.lower().replace('.', '_')}"
    return generate


def model_field_paths(model_type: type[FileTemplateModel]) -> tuple[str, ...]:
    """Describe the complete published input contract for one file model.

    The package builds each file model from the RSM fields that file consumes.
    Walking those Pydantic annotations keeps nested paths aligned without
    parsing implementation source or maintaining a second field mapping here.
    """
    discovered: list[tuple[str, ...]] = []
    for name, field in model_type.model_fields.items():
        path = (name,)
        discovered.append(path)
        _nested_model_paths(field.annotation, path, discovered)
    return tuple("/" + "/".join(path) for path in dict.fromkeys(discovered))


def _nested_model_paths(
    annotation: Any,
    path: tuple[str, ...],
    discovered: list[tuple[str, ...]],
) -> None:
    origin = get_origin(annotation)
    if origin in {Union, UnionType}:
        for member in get_args(annotation):
            if member is not type(None):
                _nested_model_paths(member, path, discovered)
        return
    if origin in {list, tuple, set, frozenset}:
        arguments = get_args(annotation)
        if arguments:
            _nested_model_paths(arguments[0], (*path, "0"), discovered)
        return
    if not inspect.isclass(annotation) or not issubclass(annotation, BaseModel):
        return
    if issubclass(annotation, RootModel):
        _nested_model_paths(annotation.model_fields["root"].annotation, path, discovered)
        return
    for name, field in annotation.model_fields.items():
        nested_path = (*path, name)
        discovered.append(nested_path)
        _nested_model_paths(field.annotation, nested_path, discovered)


def _media_type(template_media_type: str) -> str:
    if template_media_type == "json":
        return "application/json"
    if template_media_type == "yaml":
        return "application/yaml"
    if template_media_type == "zip":
        return "application/zip"
    return "text/plain; charset=utf-8"

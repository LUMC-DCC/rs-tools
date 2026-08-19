"""Framework-neutral adapters for file and repository generators."""

from rs_tools.generators.base import (
    GeneratedArtifact,
    GeneratorInputError,
    GeneratorOptions,
    GeneratorUnavailable,
    RepositoryTemplateSource,
)
from rs_tools.generators.registry import (
    GENERATORS,
    GeneratorCategory,
    GeneratorDefinition,
    build_catalogue,
    get_generator,
)
from rs_tools.generators.repository import (
    GeneratedRepository,
    generate_repository,
    render_repository,
)

__all__ = [
    "GENERATORS",
    "GeneratedArtifact",
    "GeneratedRepository",
    "GeneratorCategory",
    "GeneratorDefinition",
    "GeneratorInputError",
    "GeneratorOptions",
    "GeneratorUnavailable",
    "RepositoryTemplateSource",
    "build_catalogue",
    "generate_repository",
    "get_generator",
    "render_repository",
]

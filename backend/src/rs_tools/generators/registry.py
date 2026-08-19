"""Generator catalogue and declared RSM inputs.

Each generator declares JSON Pointer paths only. The schema service resolves the
human-readable field information shown by clients, so labels and help text never
drift from the versioned schema dependency.

Every generator shares one signature, ``generate(smp, options)``, which lets the
HTTP layer treat file generators and the repository generator identically.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from rs_files_templates import (
    BiotoolsModel,
    ChangelogModel,
    CitationModel,
    CodeMetaModel,
    CodeOfConductModel,
    ContributingModel,
    DocumentationDeploymentModel,
    DocumentationDeveloperModel,
    DocumentationLegalModel,
    DocumentationOverviewModel,
    DocumentationReferenceModel,
    DocumentationUserModel,
    FileTemplateModel,
    GovernanceModel,
    IssueTemplateModel,
    LicenseModel,
    PullRequestTemplateModel,
    ReadmeModel,
    SecurityModel,
    SupportModel,
    ZenodoModel,
)

from rs_tools.generators.base import GeneratedArtifact, GeneratorOptions
from rs_tools.generators.files import generator_for, model_field_paths
from rs_tools.generators.introspection import discover_generator_fields
from rs_tools.generators.repository import (
    REPOSITORY_TEMPLATES,
    RepositoryTemplate,
    generate_repository,
)
from rs_tools.schema.service import SchemaService

GeneratorCallable = Callable[[dict[str, Any], GeneratorOptions], GeneratedArtifact]

#: How a generated artifact is presented in the interface. ``metadata`` files
#: describe the software for machines and indexes, ``documentation`` files explain
#: the software to its audiences, ``project`` files support the repository's
#: community and maintenance, and ``repository`` builds a whole project scaffold.
GeneratorCategory = Literal["metadata", "documentation", "project", "repository"]


@dataclass(frozen=True, slots=True)
class GeneratorDefinition:
    """One entry in the public generator catalogue.

    Attributes
    ----------
    id : str
        Stable identifier used in API routes and by the frontend.
    label : str
        Name of the thing produced, such as ``CITATION.cff``. Clients compose
        their own action wording around it, so this stays a noun.
    description : str
        One sentence explaining what the artifact is for.
    filename : str
        Name the generated file is downloaded as.
    category : {'metadata', 'documentation', 'project', 'repository'}
        Presentation grouping.
    generate : callable
        ``generate(smp, options) -> GeneratedArtifact``.
    templates : tuple of RepositoryTemplate
        Selectable templates, empty for everything but the repository generator.
    fields : tuple of str
        JSON Pointers this generator reads. Discovered from the source when empty.
    """

    id: str
    label: str
    description: str
    filename: str
    category: GeneratorCategory
    generate: GeneratorCallable
    templates: tuple[RepositoryTemplate, ...] = ()
    fields: tuple[str, ...] = ()

    def as_public_metadata(self, schema: SchemaService) -> dict[str, Any]:
        """Describe this generator for the public API.

        Parameters
        ----------
        schema : SchemaService
            Used to resolve labels, descriptions, and form ordering for the
            declared JSON Pointers.

        Returns
        -------
        dict
            A JSON-serializable description including resolved field metadata.
        """
        field_paths = self.fields or discover_generator_fields(self.generate, schema)
        field_paths = (*field_paths, *schema.required_descendant_paths(field_paths))
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "filename": self.filename,
            "category": self.category,
            "fields": [schema.describe_field(path) for path in schema.order_paths(field_paths)],
            "templates": [template.as_public_metadata() for template in self.templates],
        }


@dataclass(frozen=True, slots=True)
class _FileGenerator:
    """Declaration of one generator backed by a published file model."""

    id: str
    description: str
    category: GeneratorCategory
    model: type[FileTemplateModel]


_FILE_GENERATORS: tuple[_FileGenerator, ...] = (
    _FileGenerator(
        "codemeta",
        "CodeMeta software metadata for software indexes and registries.",
        "metadata",
        CodeMetaModel,
    ),
    _FileGenerator(
        "citation-cff",
        "Citation metadata so the software can be cited correctly.",
        "metadata",
        CitationModel,
    ),
    _FileGenerator(
        "biotools",
        "bio.tools registry metadata for computational life-science software.",
        "metadata",
        BiotoolsModel,
    ),
    _FileGenerator(
        "zenodo",
        "Deposit metadata used when archiving a release on Zenodo.",
        "metadata",
        ZenodoModel,
    ),
    _FileGenerator(
        "readme",
        "A project landing page covering purpose, audiences, installation, usage, citation, "
        "and support.",
        "documentation",
        ReadmeModel,
    ),
    _FileGenerator(
        "documentation-overview",
        "An extended project overview for a documentation site.",
        "documentation",
        DocumentationOverviewModel,
    ),
    _FileGenerator(
        "documentation-user",
        "Installation and usage guidance for people using the software.",
        "documentation",
        DocumentationUserModel,
    ),
    _FileGenerator(
        "documentation-deployment",
        "Environment, dependency, service, and resource guidance for deployment.",
        "documentation",
        DocumentationDeploymentModel,
    ),
    _FileGenerator(
        "documentation-developer",
        "Development, quality-check, testing, contribution, and code-review guidance.",
        "documentation",
        DocumentationDeveloperModel,
    ),
    _FileGenerator(
        "documentation-reference",
        "A technical reference for the software's functions and interfaces.",
        "documentation",
        DocumentationReferenceModel,
    ),
    _FileGenerator(
        "documentation-legal",
        "Licensing, access conditions, costs, and regulatory information.",
        "documentation",
        DocumentationLegalModel,
    ),
    _FileGenerator(
        "license",
        "The selected software license, in full.",
        "project",
        LicenseModel,
    ),
    _FileGenerator(
        "changelog",
        "A changelog skeleton for recording released changes.",
        "project",
        ChangelogModel,
    ),
    _FileGenerator(
        "code-of-conduct",
        "The behaviour expected of everyone taking part in the project.",
        "project",
        CodeOfConductModel,
    ),
    _FileGenerator(
        "contributing",
        "How to report issues and propose changes to the project.",
        "project",
        ContributingModel,
    ),
    _FileGenerator(
        "governance",
        "Who decides what, and how those decisions are made.",
        "project",
        GovernanceModel,
    ),
    _FileGenerator(
        "security",
        "How to report a vulnerability and which versions are supported.",
        "project",
        SecurityModel,
    ),
    _FileGenerator(
        "support",
        "Where users should go for help with the software.",
        "project",
        SupportModel,
    ),
    _FileGenerator(
        "issue-templates",
        "GitHub issue forms for bug reports and feature requests, with support links.",
        "project",
        IssueTemplateModel,
    ),
    _FileGenerator(
        "pull-request-template",
        "A GitHub pull-request checklist tailored to the selected project features.",
        "project",
        PullRequestTemplateModel,
    ),
)


_REPOSITORY_GENERATOR = GeneratorDefinition(
    id="repository",
    label="repository scaffold",
    description="A complete project scaffold built from the current RSM metadata.",
    filename="repository.zip",
    category="repository",
    generate=generate_repository,
    templates=REPOSITORY_TEMPLATES,
)

GENERATORS: tuple[GeneratorDefinition, ...] = (
    *(
        GeneratorDefinition(
            id=declaration.id,
            label=declaration.model.output_name,
            description=declaration.description,
            filename=Path(declaration.model.output_name).name,
            category=declaration.category,
            generate=generator_for(declaration.model),
            fields=model_field_paths(declaration.model),
        )
        for declaration in _FILE_GENERATORS
    ),
    _REPOSITORY_GENERATOR,
)


def get_generator(generator_id: str) -> GeneratorDefinition:
    """Look up a registered generator by identifier.

    Parameters
    ----------
    generator_id : str
        Identifier from the catalogue.

    Returns
    -------
    GeneratorDefinition
        The matching generator.

    Raises
    ------
    KeyError
        If no generator has that identifier.
    """
    for generator in GENERATORS:
        if generator.id == generator_id:
            return generator
    raise KeyError(generator_id)


def build_catalogue(schema: SchemaService) -> tuple[dict[str, Any], ...]:
    """Describe every registered generator for the public API.

    Resolving one generator's fields walks the schema repeatedly, which costs
    real work. Both inputs — the packaged schema and the generator registry —
    are fixed for the lifetime of the process, so the result is built once at
    startup rather than recomputed for each request.

    Parameters
    ----------
    schema : SchemaService
        Used to resolve labels, descriptions, and form ordering.

    Returns
    -------
    tuple of dict
        One description per registered generator, in catalogue order.
    """
    return tuple(generator.as_public_metadata(schema) for generator in GENERATORS)

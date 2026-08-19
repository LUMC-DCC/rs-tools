# Generator integration

Generators live behind plain Python function boundaries in `rs_tools.generators`:

```python
def generate(smp: dict[str, Any], options: GeneratorOptions) -> GeneratedArtifact: ...
```

They must not import FastAPI, frontend code, Redis, or workspace services. The HTTP layer owns
workspace lookup and response headers; generators own metadata mapping and artifact creation. The
shared signature lets one route serve the entire catalogue.

## Current catalogue

This table is generated from `GENERATORS`, the same registry served by `/api/generators` and used
to build the tools panel.

```{generator-reference}
```

## Add a generator

Register a `GeneratorDefinition` in `backend/src/rs_tools/generators/registry.py`:

```python
GeneratorDefinition(
    id="citation-cff",
    label="CITATION.cff",
    description="Citation metadata so the software can be cited correctly.",
    filename="CITATION.cff",
    category="metadata",  # metadata | documentation | project | repository
    generate=generator_for(CitationModel),
    fields=model_field_paths(CitationModel),
)
```

The catalogue endpoint publishes the entry, and the tools panel uses its category and
declared fields. Keep `label` a noun; clients compose action text such as “Download
CITATION.cff”.

## Field discovery

Individual files are rendered by the installed `rs-files-templates` package. Adapters project only a
model's declared RSM fields before validation and delegate text or ZIP rendering to that package.
`biotools.json`, `README.md`, and the six builder-neutral documentation pages are
separate model-backed generators;
rs-tools does not bundle them or select a documentation builder. They use the `documentation`
category, while policies and contribution templates use `project` (shown as **Community files** in
the interface).

Nested field paths come from the published Pydantic contract. Labels and descriptions are resolved
from the RSM JSON Schema, so the frontend has no parallel field inventory.

When `rs-files-templates` adds or renames a published model, update `_FILE_GENERATORS`
and its tests. Registering a model exposes its RSM fields through the catalogue
endpoint; no separate frontend field mapping is required.

## Repository generation

The trusted source and template version are application configuration:

- `RS_TOOLS_REPOSITORY_TEMPLATE_URL`
- `RS_TOOLS_REPOSITORY_TEMPLATE_REVISION`

Copier's native `COPIER_CACHE_DIR` controls the reusable Git mirror. Compose mounts that cache on a
named volume. Add supported scaffolds to `REPOSITORY_TEMPLATES`; both the API and interface
selector read that tuple, while the selected identifier is passed to Copier as `template_type`.
The first entry is the default when an API caller omits `template`. The order is
generic, Python, then R.

Generation calls `copier.run_copy` with the complete validated RSM document, defaults enabled, the
configured template version, and `unsafe=True` for the trusted source-side finalization task. Use
a reviewed version tag for deployments. The output keeps
`.copier-answers.yml`, recording its source, version, language scaffold, and RSM answers for future
three-way template updates.

RSM optional objects may contain only the properties a person filled in, whereas supplying a Copier
object answer replaces that question's whole default. Before rendering, the repository adapter uses
the RSM Schema to fill omitted properties inside objects that are already present. It adds neutral
containers only when that subschema accepts them; in particular, it does not turn an omitted
structured value into an invalid empty object. Missing top-level fields stay absent and continue to
use the template's own defaults.

## Safety

Generated filenames must be fixed or sanitized; a generator never accepts a client-supplied path.
Repository generators render in a fresh temporary directory and archive only descendants of it.

Every repository passes through `validate_repository` after Copier finishes and before download or
publication. It checks file count, total and per-file size, path traversal, normalized collisions,
and credential-shaped content. Safe placeholder files such as `.env.example` are allowed, but real
environment files remain blocked. Only configure and trust a reviewed template repository.

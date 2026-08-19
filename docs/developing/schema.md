# Schema contract

The [RSM Schema](https://lumc-dcc.github.io/rsm-schema/) defines the application
metadata. The backend loads the JSON Schema packaged by `rsm-schema` and exposes it
through `GET /api/schema`.

This repository does not contain a copy of the schema or a parallel Python or
TypeScript model. Refresh the Poetry lock when updating the LUMC dependencies:

```bash
cd backend
poetry update rsm-schema rs-files-templates
poetry check --lock
poetry run pytest
```

The empty-workspace operation derives the smallest valid document from required properties,
defaults, constants, and enums. The application does not maintain a second handwritten default.

The backend supplies schema-derived field titles, descriptions, order, validation,
and generator field lists to the form. Update the schema package before adapting
schema-dependent behavior in this application.

EDAM research `topics` are a top-level collection. The form and repository generator
expose them directly, while file generators map them to documentation and formats
such as CodeMeta. Software-function entries contain operations, inputs, outputs,
commands, and notes.

`rsm_schema.validate_document()` provides pass/fail validation. `SchemaService`
compiles the bundled schema locally to collect all failures, JSON Pointer paths,
format checks, defaults, and field descriptions for the editor.

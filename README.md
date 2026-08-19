# Research Software Tools

A web application for editing Research Software Management (RSM) metadata and
generating citation and registry metadata, documentation, community files, or a
complete project scaffold. Metadata downloads include CodeMeta, CFF, bio.tools,
Zenodo, and the RSM document itself.

```text
DS Wizard, curl, or JSON upload
        │
        ▼
Published RSM JSON Schema validation
        │
        ▼
Temporary Redis workspace ──► React schema-generated form
        │                              │
        └──────────────────────────────┴──► generated files, ZIP, or a GitHub repository
```

## Architecture

- **Python 3.14 + FastAPI** serves `/api`, the OpenAPI documentation, and the built frontend.
- **React + TypeScript + Vite** renders a form generated from `GET /api/schema`, saved
  automatically as it is edited.
- **Redis** stores one JSON value per workspace and expires it after 12 hours of inactivity.
  It is the only runtime state service, and is not a permanent database.
- **One image** contains the API and the compiled frontend.

FastAPI can restart without losing active workspaces because Redis owns their state. There is no
database, filesystem persistence, user account, queue, or cleanup worker.

## Quick start

```bash
docker compose up --build
```

Open <http://localhost:8000>. Compose also starts an ephemeral Redis; no volume is created for it.

## Documentation

| Guide | For |
| --- | --- |
| [Using](docs/using/index.md) | Working with workspaces, metadata, tools, and generated repositories |
| [Deployment](docs/deployment/index.md) | Local containers, production operation, configuration, and GitHub OAuth |
| [Developing + API](docs/developing/index.md) | Source setup, tests, architecture, HTTP API, and extension points |

Route, generator, configuration, and Python references are generated during the
documentation build; see [documentation automation](docs/developing/index.md#documentation-automation).

## Development

```bash
cd backend
poetry install --with dev,docs
cd ..
backend/.venv/bin/pre-commit install
backend/.venv/bin/pre-commit run --all-files
```

See [Developing + API](docs/developing/index.md) for local services, tests, and
documentation commands.

## License

Apache-2.0. See [LICENSE](LICENSE).

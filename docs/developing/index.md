# Developing + API

This section covers local development, the HTTP API, and the form and generator
extension points.

## Run from source

Start Redis:

```bash
docker compose up redis
```

Start the backend:

```bash
cd backend
poetry install
poetry run uvicorn rs_tools.main:app --reload --port 8000
```

In another terminal, start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Vite proxies `/api` to FastAPI, so the browser sees one origin and
local development needs no CORS configuration. Swagger UI is at
<http://localhost:8000/api/docs>.

Copy `.env.example` to `.env` only when changing defaults. A shell-started backend needs those
variables exported or loaded by the process runner; Docker Compose reads `.env` automatically.

## Checks

```bash
cd backend
poetry install --with dev,docs
cd ..
backend/.venv/bin/pre-commit install
backend/.venv/bin/pre-commit run --all-files

cd backend
poetry run pytest

cd ../frontend
npm test
npm run build
```

Backend tests use an in-process Redis-compatible fake and require no services. The TypeScript
compiler has unused-local and unused-parameter checks enabled, and the production build performs a
full type check.

## Repository layout

```text
backend/src/rs_tools/
  main.py          application factory, middleware, errors, and static frontend
  config.py        typed environment configuration and documentation metadata
  api/             HTTP routes, dependencies, and URL construction
  generators/      framework-neutral file and repository generators
  schema/          schema loading, validation, and field descriptions
  storage/         storage boundary and Redis implementation
  services.py      workspace operations
  github.py        optional OAuth and publishing service
  rate_limit.py    per-client request budgets
  middleware.py    request-size and security-header middleware

frontend/src/
  pages/           route-level components
  components/      common, workspace, tools, GitHub, and schema-form features
  hooks/           loading, autosaving, connections, and viewport behavior
  lib/             pure helpers with colocated tests
  styles/          concern-based styles imported in cascade order
  api/client.ts    the only browser API client

docs/
  using/           end-user workflows
  deployment/      local and production operations
  developing/      codebase, HTTP API, contracts, and Python reference
  _ext/            generated Sphinx reference directives
```

## Design boundaries

- The [RSM Schema](schema.md) is the metadata contract. The backend validates it and the frontend
  generates the form from the exact schema served by `/api/schema`.
- [Generators](generators.md) know nothing about HTTP, Redis, or React. One registry entry reaches
  both the API and tools panel.
- Workspace storage is temporary and abstracted behind `WorkspaceStore`.
- Browser requests are centralized in `frontend/src/api/client.ts`.

The interface reads specific metadata only where it needs a label, such as the workspace title or
default repository name, and falls back safely when that property is absent.

## Documentation automation

Markdown prose lives in `docs/` and Sphinx renders it with MyST. The HTTP route table comes from
FastAPI's OpenAPI document, the tool catalogue comes from `GENERATORS`, the configuration table
comes from `Settings`, and the [Python API](python-api.md) comes from docstrings.

```bash
cd backend
poetry install --with docs
poetry run sphinx-build -b html -W --keep-going ../docs ../docs/_build/html
```

CI treats documentation warnings as errors.

## Continuous integration

| Workflow | Runs |
| --- | --- |
| `lint.yml` | Ruff checks and formatting, plus ESLint |
| `test.yml` | Pytest and Vitest |
| `build.yml` | Frontend production bundle and container image |
| `docs.yml` | Warning-free Sphinx build and GitHub Pages deployment from `main` |

Python targets 3.14, uses Ruff, and follows NumPy-style docstrings. TypeScript uses
strict compiler settings and type-aware ESLint rules.

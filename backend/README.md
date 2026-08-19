# Backend

A Python 3.14 FastAPI application. It validates every RSM document against the schema packaged by
the `rsm-schema` dependency, stores each workspace in Redis, exposes the file models supplied by
`rs-files-templates`, and serves the built frontend.

```bash
poetry install --with dev,docs
poetry run uvicorn rs_tools.main:app --reload --port 8000
```

Redis must be reachable at `redis://localhost:6379/0`, or set `RS_TOOLS_REDIS_URL`. Interactive
API documentation is at <http://localhost:8000/api/docs>.

```bash
cd ..
backend/.venv/bin/pre-commit run --all-files
cd backend
poetry run pytest
```

Tests use an in-process Redis-compatible fake, so they need no services.

| Topic | Guide |
| --- | --- |
| Layout, checks, and conventions | [Developing](../docs/developing/index.md) |
| Configuration and safety | [Deployment](../docs/deployment/index.md) |
| Routes and semantics | [HTTP API](../docs/developing/api.md) |
| Python internals | [Generated Python API](../docs/developing/python-api.md) |

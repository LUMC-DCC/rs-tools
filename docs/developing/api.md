# HTTP API

FastAPI publishes the machine-readable OpenAPI document at `/api/openapi.json` and interactive
Swagger UI at `/api/docs`. Client generators and integrations should treat OpenAPI as the route and
payload contract.

The table below is generated from the FastAPI application.

```{openapi-reference}
```

## Discoverable contracts

- `GET /api/schema` returns the exact RSM JSON Schema used for validation and form generation.
- `GET /api/generators` returns every generator identifier, download filename, category
  (`repository`, `metadata`, `documentation`, or `project`), selectable repository template, and
  schema-derived input field. The frontend presents `project` as **Community files**.
- `GET /api/openapi.json` describes request and response models for HTTP clients.

Repository generation accepts an optional `template` query parameter. Generator identifiers and
template identifiers should be discovered from `/api/generators`, not copied into a client.

## Create a workspace

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  --data @rsm.json \
  -i http://localhost:8000/api/workspaces
```

A successful response is `201 Created`. Its `Location` header points to the browser editor, so an
API client can hand the workspace to a person without constructing a frontend URL:

```http
HTTP/1.1 201 Created
Location: http://localhost:8000/w/5f7a89d7-5c44-4ce2-9b7f-6c4d84737679
Content-Type: application/json
```

`PUT` replaces the complete RSM document. The API does not support `PATCH`.
Workspace identity and timestamps are server-owned.

## Errors

| Status | Meaning |
| --- | --- |
| `400` | A GitHub connection or authorization state is invalid |
| `404` | The workspace or generator does not exist, or the workspace expired |
| `413` | The request body exceeds the configured limit |
| `422` | The RSM document or generator input is invalid |
| `429` | The client's request budget for the current window is exhausted |
| `502` | GitHub returned an upstream error |
| `503` | Redis, a generator dependency, or optional GitHub configuration is unavailable |

Schema validation failures include a `detail` message and an `errors` array containing JSON
Pointer paths. The frontend uses those paths to focus the affected form fields.

## Python internals

The routes are thin adapters around framework-neutral services and generators. Contributors who
need implementation details can use the generated [Python API](python-api.md).

# Configuration

Every setting is read once from the environment at application startup. The table below is
generated from `rs_tools.config.Settings`; adding a setting without a description or an entry in
`.env.example` fails the backend test suite.

```{configuration-reference}
```

## Production essentials

- Set `RS_TOOLS_PUBLIC_BASE_URL` to the public origin. It controls `Location` headers and the
  GitHub callback URL instead of trusting a client-supplied `Host` header.
- Set `RS_TOOLS_TRUSTED_HOSTS` to the hostnames the deployment should answer on. The local default
  `*` is inappropriate for a public service.
- Point `RS_TOOLS_REDIS_URL` at the production Redis instance.
- Keep `RS_TOOLS_CORS_ORIGINS` empty when one origin serves the interface and API. Add origins only
  for real cross-origin browser clients.
- Mount secrets and use `_FILE` variables where the platform supports them. Setting an inline
  secret and its `_FILE` counterpart together is an error.
- `RS_TOOLS_REPOSITORY_TEMPLATE_REVISION` accepts a branch, tag, or commit. Use a
  reviewed version tag for deployments. Copier executes finalization tasks from
  this source.

Copier owns its clone cache through `COPIER_CACHE_DIR`. The image sets it to a directory the
runtime user can write to, and Compose additionally backs that path with a persistent volume so the
mirror survives restarts. Its default is under `$HOME`, which the image's user cannot write to, so
never clear this variable for a container deployment. Set it explicitly when running the backend
directly and a persistent local mirror is desirable.

## Copyable environment template

This block includes the repository's actual `.env.example`, so it cannot diverge from the file
operators copy:

```{literalinclude} ../../.env.example
:language: bash
```

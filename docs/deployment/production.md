# Production deployment

Run the image with Redis and place an HTTPS reverse proxy or ingress in front of it. The container
starts uvicorn on port `8000` and serves both `/api` and the compiled single-page application.

Start from the [configuration reference](configuration.md), especially the public base URL,
trusted hosts, Redis URL, and template revision.

## Health and lifecycle

`GET /api/health` returns `200` only when the application and Redis are reachable, and `503` when
storage is unavailable. Use it as the readiness probe; the image declares the same endpoint as its
Docker healthcheck.

FastAPI can restart without losing active workspaces because Redis owns all runtime state. There
is no database migration, filesystem persistence, queue, or cleanup worker.

## Reverse proxy

The image starts uvicorn with `--proxy-headers` and defaults `FORWARDED_ALLOW_IPS` to `*`, because
the proxy address is not knowable at build time. This is safe only when the application container
cannot be reached directly.

- forward the original scheme and host;
- restrict direct network access to the proxy;
- set `RS_TOOLS_TRUSTED_HOSTS` so forged host headers are rejected;
- narrow `FORWARDED_ALLOW_IPS` to the proxy network when the platform makes that practical.

`RS_TOOLS_PUBLIC_BASE_URL` makes generated URLs correct independently of forwarded headers and is
required for GitHub publishing.

## Security boundaries

- Imports and replacements are validated against the packaged RSM Schema, including formats.
- Request bodies are capped before a route handler sees them, including chunked bodies.
- Ordinary and expensive operations have separate per-client rate limits. Requests are allowed if
  the counter store itself is unavailable.
- Workspace identifiers must be UUID4 values before they can reach a storage key.
- Responses carry a content security policy, `nosniff`, framing protection, and a no-referrer
  policy. HTTPS deployments also receive HSTS.

  Every directive names this origin. The interface loads no third-party scripts,
  styles, fonts, or images. Typefaces are bundled and served from `/assets`; tests
  reject external origins in either the page or the policy.

  `script-src` omits `'unsafe-eval'`. The form uses a display-only schema without validation
  conditionals so its rendering path does not trigger Ajv's dynamic compiler. It does not
  live-validate; the server validates the schema and returns JSON Pointer paths for
  invalid fields. Client-side live validation requires a CSP-compatible validator.
- Generated repositories are checked for unsafe paths, normalized collisions, size limits, and
  credential-shaped content before download or GitHub publication.
- GitHub tokens live only in encrypted, HttpOnly, workspace-bound cookies. The service attempts to
  revoke the OAuth grant immediately after successful publication.

Copier runs finalization tasks from the template repository with `unsafe=True`, which is required
for trusted template tasks. Treat `RS_TOOLS_REPOSITORY_TEMPLATE_URL` as executable deployment code
and restrict write access to that repository. Prefer a version tag for deployed releases once tags
are available. Keep Copier at the locked, security-patched version and do not allow request data to
select a source URL.

## Data handling

Redis stores RSM documents and rate-limit counters. It does not store accounts or GitHub tokens.
Workspace keys expire automatically, so there is no deletion job or workspace backup.
Recreating or flushing Redis discards active workspaces.

## Upgrades

Rebuild the image from the lock files, run all checks, and redeploy. Review changes
to Copier, the locked RSM Schema and file-template package, and the
repository-template revision; see the
[schema contract](../developing/schema.md) and [generator integration](../developing/generators.md).

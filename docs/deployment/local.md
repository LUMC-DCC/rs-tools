# Local deployment

Docker Compose is the shortest way to run the packaged application locally:

```bash
docker compose up --build
```

Open <http://localhost:8000>. Compose starts the application and an ephemeral Redis instance. It
does not create a Redis data volume, so active workspaces disappear when that container is removed.
The named Copier cache volume stores a Git mirror so generation does not perform a full clone on
every request.

## Local configuration

The defaults work without an `.env` file. To change them, copy the documented example and restart
the affected containers:

```bash
cp .env.example .env
docker compose up --build -d
```

Compose reads `.env` automatically. The application container overrides
`RS_TOOLS_REDIS_URL` with the Redis service address on the Compose network.

Use `GET /api/health` to confirm both the application and Redis are reachable. Interactive API
documentation is at <http://localhost:8000/api/docs>.

For live-reload servers and test commands, use the [development setup](../developing/index.md).
For local GitHub authorization, follow [GitHub publishing](github.md#local-oauth-app).

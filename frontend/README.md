# Frontend

A React + TypeScript application built with Vite. The metadata form is generated from
`GET /api/schema` with `@rjsf/core`, so no parallel TypeScript model of the schema is maintained.
Valid edits save automatically after a short debounce. The tools panel is built from
`GET /api/generators`, grouped into repositories, metadata, documentation, and community files by
the category the API assigns each generator.

Start the backend first, then:

```bash
npm install
npm run dev
```

Vite serves <http://localhost:5173> and proxies `/api` to <http://localhost:8000>.

```bash
npm run lint
npm test
npm run build
```

The production build is written to `frontend/dist` and served by FastAPI.

Layout and conventions are in [Developing + API](../docs/developing/index.md).

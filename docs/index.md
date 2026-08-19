# Research Software Tools

A web application for editing Research Software Management (RSM) metadata and
generating project files or complete repository scaffolds.

```mermaid
flowchart LR
    I["RSM JSON<br/>uploaded, pasted, or POSTed"]
    V["Schema validation<br/>rsm-schema"]
    W["Temporary workspace<br/>Redis, 12h TTL"]
    F["Generated form<br/>React + rjsf"]
    G["Generated files<br/>metadata, documentation, community files, scaffolds"]
    I --> V --> W --> F
    W --> G
```

Choose a guide:

- **[Using](using/index.md)** — create, edit, and export a workspace.
- **[Deployment](deployment/index.md)** — run locally or operate a production service.
- **[Developing + API](developing/index.md)** — work on the codebase, integrate with the HTTP API,
  and extend its contracts.

```{toctree}
:maxdepth: 2
:caption: Using
:hidden:

using/index
```

```{toctree}
:maxdepth: 2
:caption: Deployment
:hidden:

deployment/index
deployment/local
deployment/render
deployment/production
deployment/configuration
deployment/github
```

```{toctree}
:maxdepth: 2
:caption: Developing + API
:hidden:

developing/index
developing/api
developing/schema
developing/generators
developing/python-api
```

# Deployment

The application ships as one container image containing the FastAPI service and compiled React
frontend. Redis is the only state service.

Choose the path that matches the environment:

| Environment | Guide | Intended use |
| --- | --- | --- |
| Local containers | [Local deployment](local.md) | Evaluation, demonstrations, and testing production-like packaging |
| Managed host | [Deploying on Render](render.md) | Deploying from this repository with no server to run |
| Public HTTPS service | [Production deployment](production.md) | Shared service behind a reverse proxy or ingress |
| Source checkout | [Developing](../developing/index.md) | Backend and frontend changes with live reload |

All deployments use the same [configuration reference](configuration.md). GitHub repository
publishing is optional and has its own [OAuth setup guide](github.md).

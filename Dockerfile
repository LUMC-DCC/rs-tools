# syntax=docker/dockerfile:1.7

FROM node:22-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim AS backend-build
ARG POETRY_VERSION=2.4.0
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
# git is needed to install the locked rsm-schema and rs-files-templates
# dependencies from their Git URLs.
RUN apt-get update \
  && apt-get install -y --no-install-recommends git \
  && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"
RUN python -m venv "${VIRTUAL_ENV}"
WORKDIR /build/backend
COPY backend/pyproject.toml backend/poetry.lock ./
COPY backend/README.md ./
COPY backend/src/ ./src/
RUN poetry install --only main --no-root --no-interaction --no-ansi
RUN pip install --no-cache-dir --no-deps .
RUN python -c "import rs_tools.main"

FROM python:3.14-slim AS runtime

ENV PATH="/opt/venv/bin:${PATH}"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV RS_TOOLS_FRONTEND_DIST=/app/frontend/dist
# The proxy is a separate container with an address this image cannot know, so
# forwarded headers are accepted from any peer. That is only safe because the
# container is not reachable directly: publish it behind a trusted proxy, and
# set RS_TOOLS_TRUSTED_HOSTS so a forged Host header is refused regardless.
ENV FORWARDED_ALLOW_IPS=*
# Copier caches a Git mirror of the template. Its default location is
# $HOME/.cache, and HOME is /app, which the runtime user cannot write to, so
# without this every repository generation fails on a permission error. Pointed
# at the one directory the image grants that user.
ENV COPIER_CACHE_DIR=/var/cache/rs-tools/copier
# Overridden by hosts that assign a port; 8000 keeps compose and `docker run`
# working unchanged.
ENV PORT=8000

WORKDIR /app

# git stays in the runtime image because Copier clones the template
# repository when generating a project scaffold.
RUN apt-get update \
  && apt-get install -y --no-install-recommends git \
  && rm -rf /var/lib/apt/lists/*

RUN groupadd --system rs-tools \
  && useradd --system --gid rs-tools --home-dir /app rs-tools \
  && mkdir -p /var/cache/rs-tools \
  && chown -R rs-tools:rs-tools /var/cache/rs-tools

COPY --from=backend-build /opt/venv /opt/venv
COPY --from=frontend-build /build/frontend/dist /app/frontend/dist

USER rs-tools

EXPOSE 8000

# Exec form, with Python reading the environment itself: no shell is involved,
# so there is no quoting to get wrong.
#
# The request goes to the loopback address but carries the first trusted host as
# its Host header. Without that, every deployment that sets RS_TOOLS_TRUSTED_HOSTS
# — which is every correct one — has its own healthcheck rejected as a forged
# host and reports the container unhealthy. Sending the header keeps the guard
# exactly as strict as configured instead of punching a hole in it for probes.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import os,urllib.request as u;h=os.environ.get('RS_TOOLS_TRUSTED_HOSTS','*').split(',')[0].strip();r=u.Request('http://127.0.0.1:'+os.environ['PORT']+'/api/health',headers={} if h in ('','*') else {'Host':h});u.urlopen(r,timeout=3)"]

# Shell form on purpose: the exec form does not expand ${PORT}, and platforms
# that pick the port for the container (Render assigns 10000) need it read at
# start. `exec` keeps uvicorn as PID 1, so it still receives stop signals.
CMD exec uvicorn rs_tools.main:app --host 0.0.0.0 --port "${PORT}" --proxy-headers

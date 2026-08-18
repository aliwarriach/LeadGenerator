# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1 — build the SPA
# ---------------------------------------------------------------------------
FROM node:20-alpine AS frontend

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

# The API base URL comes from frontend/.env.production (VITE_API_BASE_URL=/),
# which `vite build` loads for the production mode automatically. Deliberately
# NOT passed as an environment variable: a bare "/" is mangled into a Windows
# path by MSYS-based shells (confirmed - Git Bash turned it into
# "C:/Program Files/Git/"), which would silently bake a broken base URL into
# the bundle. A committed file cannot be rewritten that way.
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2 — runtime
# ---------------------------------------------------------------------------
# Python 3.12, not the Playwright base image: that ships 3.10, and this code
# uses enum.StrEnum, which needs 3.11+.
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copied before the rest of the source so the dependency layer is only rebuilt
# when requirements actually change.
COPY backend/requirements.txt ./
# `playwright` the Python package is imported at startup (main -> workers.queue
# -> discovery_worker -> scrapers), so it has to be installed. `playwright
# install` is deliberately NOT run: no browser is ever launched in this image —
# scraping runs on an operator machine — and downloading Chromium would add
# ~150 MB and minutes of cold start for nothing.
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend /build/dist ./frontend_dist
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENV FRONTEND_DIST_DIR=/app/frontend_dist

# Runs as root by default otherwise, which removes a containment layer if any
# other finding in this app escalates to code execution — a compromised
# runtime process would have no OS-level barrier left. See SecurityIssues.md
# L-2. `screenshots`/`browser_profiles` aren't created by the API process
# itself, but `chown` covers them too in case a shared image path ever does.
RUN groupadd --system app && useradd --system --gid app --home /app --no-create-home appuser \
    && chown -R appuser:app /app
USER appuser

# Overridden by the platform's injected $PORT; declared for local `docker run`.
EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

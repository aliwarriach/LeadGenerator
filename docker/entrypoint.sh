#!/usr/bin/env bash
# Container entrypoint: bring the schema up to date, then serve.
#
# Migrations run here rather than from a separate job because the deployment
# target runs a single revision at a time, so there is no concurrent-migration
# race to avoid. A failed migration fails container startup, which fails the
# deploy — the intended outcome, since serving against a stale schema is worse.
set -euo pipefail

echo "Applying database migrations..."
alembic upgrade head

echo "Starting API on port ${PORT:-8080}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"

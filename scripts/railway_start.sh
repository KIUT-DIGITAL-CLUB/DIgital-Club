#!/usr/bin/env sh
# Entrypoint for hosted deployments (Railway and friends).
#
# A persistent volume mounted at /app/app/static/uploads shadows whatever was
# baked into the image at that path, so the volume starts out empty. This seeds
# it once from the copy the Dockerfile stashed at /app/seed_uploads. `cp -n`
# never overwrites a file that already exists, so re-running is safe and files
# uploaded by users are never touched.
set -e

UPLOADS_DIR="/app/app/static/uploads"
SEED_DIR="/app/seed_uploads"

if [ -d "$SEED_DIR" ]; then
    mkdir -p "$UPLOADS_DIR"
    cp -rn "$SEED_DIR"/. "$UPLOADS_DIR"/ 2>/dev/null || true
    echo "[start] uploads seeded into $UPLOADS_DIR"
fi

exec gunicorn -c gunicorn_conf.py main:app

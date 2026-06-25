#!/usr/bin/env sh
# Apply DB migrations, then run whatever command was passed (default: runner).
set -e

echo "[entrypoint] applying migrations -> $DATABASE_URL"
python -m alembic upgrade head

echo "[entrypoint] starting: $*"
exec "$@"

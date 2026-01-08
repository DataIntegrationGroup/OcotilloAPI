#!/usr/bin/env bash
# Load environment variables from .env and run the staging backfill.
# Usage: ./run_backfill.sh [--batch-size N]

set -euo pipefail

ENV_FILE=".env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE; aborting." >&2
  exit 1
fi

# Export variables from .env
set -a
source "$ENV_FILE"
set +a

uv run alembic upgrade head

# Forward any args (e.g., --batch-size 500)
python -m transfers.backfill.staging "$@"

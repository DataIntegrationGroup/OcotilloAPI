# Image for the `gwl-export-<env>` Cloud Run job (OCO-79).
#
# One image, five steps: Dagster launches the job with the step as the
# container args (`snapshot --snapshot-id ... --root gs://...`), so the
# entrypoint is the worker module and CMD is empty.
#
# Build from the repository root -- the worker imports db/ for the snapshot:
#
#   docker build -f docker/gwl_export/Dockerfile -t <region>-docker.pkg.dev/<project>/ocotillo/gwl-export:<sha> .
FROM python:3.13-slim

# Same build prerequisites as the API image (psycopg2 / pg8000 wheels need
# none, but a source fallback must not fail the build).
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.7.17 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/usr/local \
    PYTHONUNBUFFERED=1

# Dependencies first, so a code-only change reuses this layer. `ingestion`
# carries pyarrow; `--no-dev` keeps test tooling out.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --group ingestion --no-install-project

COPY . .
RUN uv sync --locked --no-dev --group ingestion

# Never root in the job.
RUN useradd --system --uid 10001 worker
USER worker

ENTRYPOINT ["python", "-m", "automated_ingestion.exports.groundwater_levels.worker"]

FROM python:3.13-slim AS base

# install system dependencies for psycopg2 and uv
RUN apt-get update && apt-get install -y curl gcc libpq-dev

# install curl
RUN apt-get update && apt-get install -y curl

# install uv (fast dependency manager)
RUN curl -Ls https://astral.sh/uv/install.sh | sh -s -- v0.7.17 && \
    cp /root/.local/bin/uv /usr/local/bin/uv

# set workdir
WORKDIR /app

# copy the full project source
COPY . .

run ls -la

# install dependencies using uv
ENV UV_PROJECT_ENVIRONMENT="/usr/local/"
RUN uv sync --locked --no-dev

# migrate with Alembic
RUN python db/base.py create_all

# expose FastAPI's default dev port
EXPOSE 8000

# default command (run database migrations and the FastAPI development server)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

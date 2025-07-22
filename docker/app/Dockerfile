FROM python:3.13-slim AS base

# install system dependencies for psycopg2 and uv
RUN apt-get update && apt-get install -y curl gcc libpq-dev

# install curl
RUN apt-get update && apt-get install -y curl

# install uv (fast dependency manager)
RUN curl -Ls https://astral.sh/uv/install.sh | sh -s -- v0.7.17 && \
    cp /root/.local/bin/uv /usr/local/bin/uv

# install postgresql client
RUN apt-get update && apt-get install -y postgresql-client

# set workdir
WORKDIR /app

# copy the full project source
COPY . .

# install dependencies using uv
ENV UV_PROJECT_ENVIRONMENT="/usr/local/"
RUN uv sync --locked

# expose FastAPI's default dev port
EXPOSE 8000

# set environment variables for database connection
RUN chmod +x entrypoint.sh

# default command (run database migrations and the FastAPI development server)
CMD ["sh", "entrypoint.sh"]

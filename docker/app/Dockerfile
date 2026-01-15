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

# Define an optional build argument
ARG INSTALL_DEV=false
ENV INSTALL_DEV=${INSTALL_DEV}

# Install dependencies using uv (conditionally include dev dependencies)
ENV UV_PROJECT_ENVIRONMENT="/usr/local/"
RUN if [ "$INSTALL_DEV" = "true" ]; then \
      echo "Installing all groups (including dev)..." && \
      uv sync --locked --all-groups; \
    else \
      echo "Installing only production dependencies..." && \
      uv sync --locked; \
    fi

# Expose port (Render uses $PORT env variable, defaults to 8000 locally)
ARG PORT=8000
EXPOSE ${PORT}

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Default command: runs migrations and starts gunicorn (production) or uvicorn (dev)
# Gunicorn is used by default; set RELOAD_ENABLED=true for local development with uvicorn
CMD ["sh", "entrypoint.sh"]

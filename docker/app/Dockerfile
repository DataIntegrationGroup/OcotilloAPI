FROM python:3.13-slim AS base

# install uv (fast dependency manager)
RUN curl -Ls https://astral.sh/uv/install.sh | sh -s -- v0.7.17 && \
    cp /root/.local/bin/uv /usr/local/bin/uv

# set workdir
WORKDIR /app

# copy dependencies first to leverage Docker cache
COPY pyproject.toml uv.lock* requirements*.txt* ./

ENV UV_PROJECT_ENVIRONMENT="/usr/local/"
RUN uv sync --locked --no-dev

# copy the full project source
COPY ./.. .

# expose FastAPI's default dev port
EXPOSE 8000

# default command (run the development server)
CMD []

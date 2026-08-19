#!/usr/bin/env bash
# Runs inside the Dagster+ *image* build, after the repository has been copied to
# /opt/dagster/app and the pinned requirements installed.
#
# Only the Docker fallback path reaches this script. The default PEX path builds
# no image: `dagster_cloud_cli`'s source-pex builder runs its own
# `uv pip install --target ... --no-deps .` over this repository, which is the
# same install by a different route. Both CD_dagster_*.yml workflows document
# the switch between the two.
#
# Installs this repository as a package so `db`, `domain`, `services`, `core`,
# and `schemas` resolve from site-packages. Without it they are importable only
# while /opt/dagster/app happens to be on sys.path -- true for the process that
# loads the code location, not for the process that executes a step, which is
# where the loader's imports run. That difference is invisible locally, where an
# editable install puts the repository on the path unconditionally.
#
# --no-deps because the pinned, hashed requirements are already installed and
# this must not resolve anything on top of them.
set -euo pipefail
pip install --no-deps .

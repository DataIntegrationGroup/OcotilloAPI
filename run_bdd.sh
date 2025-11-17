#!/usr/bin/env bash
set -e

# -----------------------------
# run_bdd.sh
# Runs backend BDD tests using feature files from the shared BDD repo
# -----------------------------

# Ensure we're in the backend repo root
cd "$(dirname "$0")"
echo "🏁 Starting BDD test run..."

# Create and activate virtual environment
if [ ! -d ".venv" ]; then
  echo "🧱 Creating virtual environment..."
  python3 -m venv venv
fi

# bin for Unix, Scripts for Windows
if [ -d ".venv/bin" ]; then
  source .venv/bin/activate
else
  source .venv/Scripts/activate
fi

# Install dependencies
echo "📦 Installing Python dependencies..."
uv sync
#uv pip install --upgrade pip
#uv pip install -r requirements.txt || true
#uv pip install behave requests

# Checkout or update BDD repo
if [ ! -d "../OcotilloBDD" ]; then
  echo "📂 Cloning BDD repository..."
  git clone https://github.com/DataIntegrationGroup/OcotilloBDD.git ../OcotilloBDD
else
  echo "🔄 Updating existing BDD repository..."
  cd ../OcotilloBDD && git checkout main && git pull && cd - >/dev/null
fi

# Copy backend features
echo "📋 Syncing backend features..."
mkdir -p tests/features
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OSTYPE" == "win64" || "$OSTYPE" == "cygwin" ]]; then
  # Windows
  cp -r ../OcotilloBDD/features/backend/. tests/features/
else
  # Unix/Linux/Mac
  rsync -a ../OcotilloBDD/features/backend/ tests/features/
fi

# Run Behave tests
echo "🚀 Running Behave tests..."
export PYTHONPATH="$PWD"
export BASE_URL=${BASE_URL:-http://localhost:8000}
#uv run behave tests/features/location-notes.feature --tags=@backend
#uv run behave tests/features/well-notes.feature --tags=@backend
#uv run behave tests/features --tags=@backend
#uv run behave tests/features/sensor-notes.feature --tags=@backend

# uv run behave tests/features/transducer-data-response.feature

#uv run behave tests/features/transducer-data-response.feature \
#  tests/features/thing-type-path-parameters.feature \
#  tests/features/thing-query-parameters.feature

#uv run behave tests/features/well-inventory-csv.feature
uv run behave tests/features/well-core-information.feature --capture

echo "✅ BDD test run complete."

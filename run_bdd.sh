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
source .venv/bin/activate

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
  cd ../OcotilloBDD && git pull && cd - >/dev/null
fi

# Copy backend features
echo "📋 Syncing backend features..."
mkdir -p tests/features
rsync -a ../OcotilloBDD/features/backend/ tests/features/

# Run Behave tests
echo "🚀 Running Behave tests..."
export PYTHONPATH="$PWD"
export BASE_URL=${BASE_URL:-http://localhost:8000}
#uv run behave tests/features/location-notes.feature --tags=@backend
#uv run behave tests/features/well-notes.feature --tags=@backend
#uv run behave tests/features --tags=@backend
#uv run behave tests/features/sensor-notes.feature --tags=@backend


uv run behave tests/features --tags=@backend --tags=@production

echo "✅ BDD test run complete."

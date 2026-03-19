#!/bin/bash
# start_api.sh — Start ARIA FastAPI backend
# Run this in Termux: bash start_api.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== ARIA Backend ==="
echo "Installing dependencies..."
pip install -r requirements_api.txt -q

echo "Starting FastAPI server on http://0.0.0.0:8000 ..."
echo "Flutter app should connect to http://localhost:8000"
echo ""

python -m uvicorn router:app --host 0.0.0.0 --port 8000 --reload

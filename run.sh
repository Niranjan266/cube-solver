#!/usr/bin/env bash
# Rubik's Cube Solver - one-click start (macOS / Linux)
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Creating a virtual environment..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing dependencies (first run only)..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -r backend/requirements.txt

cat <<'EOF'

==========================================================
  Cube Solver is starting.
  Open  http://127.0.0.1:8000  in your browser.
  Press Ctrl+C here to stop it.
==========================================================

EOF

cd backend
exec python -m uvicorn app:app --host 127.0.0.1 --port 8000

#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
elif [[ -f ../mcp_search/.env ]]; then
  echo "Using MCP_ENDPOINT from scripts/mcp_search/.env"
  set -a
  source ../mcp_search/.env
  set +a
else
  echo "Missing .env — copy .env.example to .env and add your xiaozhi endpoint."
  exit 1
fi

PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done

if [[ -z "$PYTHON" ]]; then
  echo "Python 3.11+ is required. Install with: brew install python@3.12"
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "Creating .venv with $PYTHON..."
  "$PYTHON" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q -r requirements.txt

if [[ ! -f .google-token.json ]]; then
  echo "No .google-token.json yet — the first calendar tool call opens a browser for OAuth."
  echo "Or run: python server.py --authorize"
fi

echo "Starting Google Calendar MCP bridge (Ctrl+C to stop)..."
python mcp_pipe.py

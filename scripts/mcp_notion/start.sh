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

if ! command -v node >/dev/null 2>&1 || ! command -v npx >/dev/null 2>&1; then
  echo "Node.js is required. Install it with: brew install node"
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
  echo "Python 3.11+ is required."
  exit 1
fi

if [[ ! -d .venv ]]; then
  "$PYTHON" -m venv .venv
fi

source .venv/bin/activate
python -m pip install -q -r requirements.txt

echo "Starting Notion MCP bridge (Ctrl+C to stop)..."
echo "The first run opens a browser. Authorize ONLY the 'Desk Chat Notes' page."
python mcp_pipe.py

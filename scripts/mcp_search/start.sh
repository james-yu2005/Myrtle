#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy .env.example to .env and add your keys."
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is required (v20+). Install from https://nodejs.org/"
  exit 1
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "npx not found. Reinstall Node.js from https://nodejs.org/"
  exit 1
fi

python3 -m pip install -q -r requirements.txt

echo "Starting Tavily search MCP bridge (Ctrl+C to stop)..."
python3 mcp_pipe.py

#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy .env.example to .env and add your keys."
  exit 1
fi

# Prefer Homebrew / newer Pythons; python-kasa 0.10+ needs 3.11+.
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

ver="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
major="${ver%%.*}"
minor="${ver#*.}"
if (( major < 3 || (major == 3 && minor < 11) )); then
  echo "Found $PYTHON ($ver); python-kasa needs Python 3.11+."
  echo "Install with: brew install python@3.12"
  exit 1
fi

# Local venv avoids Homebrew PEP 668 "externally-managed-environment".
if [[ ! -d .venv ]]; then
  echo "Creating .venv with $PYTHON..."
  "$PYTHON" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

pip install -q -r requirements.txt

echo "Starting Tapo lights MCP bridge (Ctrl+C to stop)..."
python mcp_pipe.py

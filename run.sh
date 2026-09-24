#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
export PIP_CACHE_DIR="$VENV_DIR/.pip-cache"
export PIP_DISABLE_PIP_VERSION_CHECK=1

cd "$PROJECT_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --quiet -r "$PROJECT_DIR/requirements.txt"

exec "$VENV_DIR/bin/python" "$PROJECT_DIR/main.py" "$@"

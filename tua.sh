#!/usr/bin/env bash
# for unix

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"

PYTHON_BIN=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "tua: couldn't find python3 (or python) on your PATH." >&2
    echo "     tua needs a Python 3 interpreter to run its compiler." >&2
    exit 1
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/tuac.py" "$@"

#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [[ "${1:-}" == --help ]]; then echo 'PV_PYTHON=/path/to/python bash scripts/01_bootstrap.sh'; exit 0; fi
"${PV_PYTHON:-python3}" -m venv .venv
if [[ -f .venv/Scripts/python.exe ]]; then PY=.venv/Scripts/python.exe; else PY=.venv/bin/python; fi
"$PY" -m pip install --upgrade 'pip>=26.1.2,<27'
"$PY" -m pip install -c constraints.txt -e '.[dev]'

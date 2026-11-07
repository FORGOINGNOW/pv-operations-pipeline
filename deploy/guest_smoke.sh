#!/usr/bin/env bash
# Run inside the extracted project directory in an Ubuntu guest.
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
command -v python3 >/dev/null
python3 -c 'import sys; assert sys.version_info >= (3, 12), "Python >=3.12 required"'
if [[ ! -x .venv/bin/python ]]; then
  if ! python3 -m venv .venv; then
    printf '%s\n' 'Guest Python venv support is unavailable. Install python3-venv in the guest, then rerun.' >&2
    exit 2
  fi
fi
.venv/bin/python -m pip install --upgrade -c constraints.txt pip
.venv/bin/python -m pip install -c constraints.txt -e '.[dev]'
bash scripts/00_doctor.sh --config configs/smoke.yaml
.venv/bin/python -m pytest -q
while IFS= read -r -d '' file; do bash -n "$file"; done < <(find scripts deploy -name '*.sh' -print0)
bash scripts/90_demo.sh --config configs/smoke.yaml --run-id vm-smoke
.venv/bin/python scripts/verify_sql.py --root runtime/smoke
.venv/bin/python scripts/validate_contracts.py --root runtime/smoke
.venv/bin/python scripts/verify_recovery.py
.venv/bin/python scripts/verify_late.py
printf '%s\n' 'VM_SMOKE_SUCCESS: runtime/smoke/dashboard/dashboard.html'

#!/usr/bin/env bash
set -Eeuo pipefail
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd -- "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}" OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-2}"
if [[ -n "${PV_PYTHON:-}" ]]; then PYTHON="$PV_PYTHON"
elif [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then PYTHON="$PROJECT_ROOT/.venv/bin/python"
elif [[ -f "$PROJECT_ROOT/.venv/Scripts/python.exe" ]]; then PYTHON="$PROJECT_ROOT/.venv/Scripts/python.exe"
else PYTHON=python; fi
CONFIG=configs/smoke.yaml
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
ROOT=""; DATE=""; START=""; END=""; DRY=0; FORCE=0; LATE=0
while (($#)); do
  case "$1" in
    --config|--root|--date|--start|--end|--run-id)
      [[ $# -ge 2 && -n "$2" ]] || { echo "Missing value: $1" >&2; exit 2; }
      case "$1" in
        --config) CONFIG="$2";; --root) ROOT="$2";; --date) DATE="$2";;
        --start) START="$2";; --end) END="$2";; --run-id) RUN_ID="$2";;
      esac; shift 2;;
    --dry-run) DRY=1; shift;; --force) FORCE=1; shift;; --allow-late) LATE=1; shift;;
    --help|-h) echo "Usage: $0 [--config FILE] [--date YYYY-MM-DD | --start YYYY-MM-DD --end EXCLUSIVE] [--root DIR] [--run-id ID] [--dry-run] [--force] [--allow-late]"; exit 0;;
    *) echo "Unknown argument: $1" >&2; exit 2;;
  esac
done
[[ "$RUN_ID" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'Invalid run-id' >&2; exit 2; }
[[ -f "$CONFIG" ]] || { echo 'Config not found' >&2; exit 2; }
if [[ -z "$ROOT" ]]; then
  PROFILE="$("$PYTHON" -c 'import sys,yaml;print(yaml.safe_load(open(sys.argv[1],encoding="utf-8"))["profile"])' "$CONFIG")"
  [[ "$PROFILE" =~ ^[a-zA-Z0-9_-]+$ ]] || exit 2
  ROOT="$PROJECT_ROOT/runtime/$PROFILE"
fi
ROOT="$("$PYTHON" -c 'from pathlib import Path;import sys;print(Path(sys.argv[1]).resolve().as_posix())' "$ROOT")"
ARGS=(--config "$CONFIG" --root "$ROOT" --run-id "$RUN_ID")
[[ -z "$DATE" ]] || ARGS+=(--date "$DATE")
[[ -z "$START" ]] || ARGS+=(--start "$START")
[[ -z "$END" ]] || ARGS+=(--end "$END")
(( ! DRY )) || ARGS+=(--dry-run)
(( ! FORCE )) || ARGS+=(--force)
(( ! LATE )) || ARGS+=(--allow-late)
LOCKED=0; RUN_TEMP=""
cleanup() {
  local rc=$?
  trap - EXIT
  if [[ -n "$RUN_TEMP" && "$RUN_TEMP" == "$ROOT/tmp/$RUN_ID."* && -d "$RUN_TEMP" ]]; then
    # Only empty per-run scratch directory; never recursive deletion.
    rmdir -- "$RUN_TEMP" || true
  fi
  if (( LOCKED )); then
    rm -f -- "$ROOT/.pipeline.lock/owner.json"
    rmdir -- "$ROOT/.pipeline.lock" || true
  fi
  if (( rc != 0 )); then
    "$PYTHON" -c 'import json,sys; print(json.dumps({"run_id":sys.argv[1],"step":"shell_exit","exit_code":int(sys.argv[2])}))' "$RUN_ID" "$rc" >&2
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'rc=$?; printf "ERROR line=%s exit=%s run_id=%s\n" "$LINENO" "$rc" "$RUN_ID" >&2; exit "$rc"' ERR
acquire_lock() {
  (( ! DRY )) || return 0
  mkdir -p -- "$ROOT/tmp"
  if ! mkdir -- "$ROOT/.pipeline.lock" 2>/dev/null; then
    echo "Pipeline locked: $ROOT/.pipeline.lock (inspect owner before manual stale-lock recovery)" >&2
    exit 73
  fi
  LOCKED=1
  "$PYTHON" -c 'import json,os,socket,sys; from pathlib import Path; Path(sys.argv[1]).write_text(json.dumps({"run_id":sys.argv[2],"pid":os.getppid(),"host":socket.gethostname()}))' "$ROOT/.pipeline.lock/owner.json" "$RUN_ID"
  RUN_TEMP="$(mktemp -d "$ROOT/tmp/$RUN_ID.XXXXXX")"
}
run_step() {
  local step="$1" attempt=1 rc=0
  while :; do
    # Conditional context intentionally handles exit status; ERR does not fire here.
    if "$PYTHON" -m pv_pipeline.cli "$step" "${ARGS[@]}" --attempt "$attempt"; then
      return 0
    else rc=$?; fi
    if (( rc != 75 || attempt >= 3 )); then return "$rc"; fi
    echo "Temporary failure: $step; retry $attempt/3" >&2
    sleep "$((1 << (attempt-1)))"
    attempt=$((attempt+1))
  done
}
pipeline() {
  acquire_lock
  for step in generate collect clean aggregate features train score evaluate dashboard report verify; do
    run_step "$step"
  done
  if (( ! DRY )); then run_step watermark; fi
  printf 'PIPELINE_SUCCESS run_id=%s root=%s\n' "$RUN_ID" "$ROOT"
}

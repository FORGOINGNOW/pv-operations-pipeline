"""Actual incremental clean/backfill and raw integrity checks in an isolated runtime."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from pv_pipeline.core import digest

project = Path(__file__).resolve().parents[1]
os.chdir(project)
root = project / "runtime" / ("late-" + str(time.time_ns()))
day = "2025-01-01"
raw = root / "raw" / f"date={day}"
shutil.copytree(project / "runtime/smoke/raw" / f"date={day}", raw)
base = [sys.executable, "-m", "pv_pipeline.cli"]
args = ["--config", "configs/smoke.yaml", "--root", str(root), "--date", day, "--run-id", "late-test"]
env = {**os.environ, "PYTHONUTF8": "1", "OMP_NUM_THREADS": "2"}


def run(step, extra=(), expect=0):
    result = subprocess.run(base + [step] + args + list(extra), capture_output=True, env=env)
    assert result.returncode == expect, result.stderr.decode("utf-8", errors="replace")


# Direct stage functions are used because this check intentionally isolates quality semantics.
# CLI receipts still require source dependencies; generate first verifies immutable raw reuse.
run("generate")
run("collect")
run("clean")
before = json.loads((root / "quality" / f"{day}.json").read_text())
run("clean", ["--allow-late"])
after = json.loads((root / "quality" / f"{day}.json").read_text())
assert after["retained"] == before["retained"] + 1
assert after["quarantined"] == before["quarantined"] - 1
assert after["reconciliation_ok"]
# Isolated copied source corruption must fail integrity verification and never change DWD.
dwd = root / "dwd" / f"date={day}" / "part.parquet"
checksum = digest(dwd)
with open(raw / "telemetry.jsonl", "ab") as f:
    f.write(b"corrupted\n")
run("collect", ["--force"], expect=1)
assert digest(dwd) == checksum
evidence = {
    "synthetic": True,
    "before": before,
    "after": after,
    "late_row_recovered": 1,
    "raw_checksum_corruption_exit": 1,
    "derived_output_unchanged_on_integrity_failure": True,
}
out = project / "reports/evidence/late-backfill.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
print(json.dumps(evidence, indent=2))

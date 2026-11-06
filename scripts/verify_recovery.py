"""Real Bash failure/retry/locking/resume/idempotence checks; no filesystem deletion."""

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

project = Path(__file__).resolve().parents[1]
os.chdir(project)
bash = os.environ.get("PV_BASH") or shutil.which("bash")
if os.name == "nt":
    bash = r"D:\SoftWare\RealApp\Git\Git\bin\bash.exe"
root = project / "runtime" / ("recovery-" + str(time.time_ns()))
args = [
    bash,
    "scripts/90_demo.sh",
    "--config",
    "configs/smoke.yaml",
    "--date",
    "2025-01-01",
    "--root",
    root.as_posix(),
    "--run-id",
    "recovery-test",
]


def run(command, env=None):
    p = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    return p.returncode, p.stdout[-3000:], p.stderr[-1000:]


rc, _, err = run(args, {**os.environ, "PV_FAIL_STEP": "clean"})
assert rc == 1, (rc, err)
assert not (root / "watermark.json").exists()
assert not (root / "dwd/date=2025-01-01/part.parquet").exists()
assert not (root / "state/clean/2025-01-01.json").exists()
rc, _, err = run(args, {**os.environ, "PV_TRANSIENT_ONCE": "clean"})
assert rc == 0, err
assert (root / "watermark.json").exists()


def checksums():
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.glob("state/*/*.json")
    }


before = checksums()
rc, stdout, err = run(args)
assert rc == 0, err
assert before == checksums()
assert "verified_content" in stdout
lock = root / ".pipeline.lock"
lock.mkdir()
(lock / "owner.json").write_text('{"test":"lock contention"}')
rc, _, _ = run(args)
assert rc == 73
(lock / "owner.json").unlink()
lock.rmdir()
evidence = {
    "synthetic": True,
    "failure_exit": 1,
    "watermark_after_failure": False,
    "completed_clean_partition_after_failure": False,
    "transient_retry_exit": 0,
    "idempotent_receipts": before == checksums(),
    "lock_conflict_exit": rc,
    "root": str(root),
    "assertions": "all passed",
}
out = project / "runtime/recovery_evidence.json"
out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
print(json.dumps(evidence, indent=2))

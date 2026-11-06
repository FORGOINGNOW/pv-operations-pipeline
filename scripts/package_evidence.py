"""Derive small, reviewable report samples from actual runtime outputs."""

import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--root", default="runtime/demo")
p.add_argument("--profile", default="demo")
p.add_argument("--run-id", help="Restrict timing/memory evidence to one observed run")
a = p.parse_args()
root = Path(a.root)
target = Path("reports") / a.profile
target.mkdir(parents=True, exist_ok=True)
for name in [
    "evaluation.json",
    "models/manifest.json",
    "models/rolling_backtest.json",
    "reports/weekly.md",
    "reports/monthly.md",
    "reports/quarterly.md",
    "reports/data_quality.json",
    "reports/model_validation.md",
    "outbox/workorders.json",
]:
    source = root / name
    dest = target / ("model_manifest.json" if name == "models/manifest.json" else source.name)
    shutil.copyfile(source, dest)
if (root / "quality_evaluation.json").exists():
    shutil.copyfile(root / "quality_evaluation.json", target / "quality_evaluation.json")
logs = []
for path in sorted((root / "logs").glob("*.jsonl")):
    logs.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
if a.run_id:
    logs = [r for r in logs if r["run_id"] == a.run_id]
by_step = defaultdict(
    lambda: {"partitions_executed": 0, "sum_step_seconds": 0.0, "max_end_step_rss_mib": 0.0}
)
for r in logs:
    s = by_step[r["step"]]
    s["partitions_executed"] += 1
    s["sum_step_seconds"] += r["duration"]
    s["max_end_step_rss_mib"] = max(s["max_end_step_rss_mib"], r["rss_mib"])
manifests = [
    json.loads(p.read_text(encoding="utf-8")) for p in sorted((root / "raw").glob("date=*/manifest.json"))
]
sizes = {
    layer: sum(p.stat().st_size for p in (root / layer).rglob("*") if p.is_file())
    for layer in ["raw", "ods", "dwd", "features", "scored", "ads"]
}
evidence = {
    "synthetic": True,
    "profile": a.profile,
    "observed_run_ids": sorted({r["run_id"] for r in logs}),
    "partitions": len(manifests),
    "start": manifests[0]["date"],
    "last_date_inclusive": manifests[-1]["date"],
    "grid_rows": sum(m["grid_rows"] for m in manifests),
    "raw_rows": sum(m["rows"] for m in manifests),
    "steps": dict(by_step),
    "disk_bytes_by_layer": sizes,
    "memory_note": "RSS sampled at step completion, NOT peak RSS; includes interpreter, excludes other processes",
    "timing_note": "actual sums of step body durations; excludes interpreter startup, hashing and Shell overhead",
    "source_root": root.as_posix(),
    "config_sha256": manifests[0]["config_sha256"],
}
(target / "performance.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in evidence.items() if k not in ["steps"]}, indent=2))

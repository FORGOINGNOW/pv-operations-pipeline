"""Post-hoc evaluation of known transport mutations, separate from equipment truth.

Ground truth is reconstructed from the versioned deterministic injection schedule,
NOT from observed quality flags. IDs are only evaluation join keys. The pipeline's
clean/train/score modules never read this sidecar. Unscheduled corruptions and
unobservable single-sample sensor-stuck changes are explicitly outside this score.
"""

import argparse
import json
from pathlib import Path

import pandas as pd

from pv_pipeline.analytics import classification
from pv_pipeline.core import config, json_write, parquet_read
from pv_pipeline.quality import CASES

p = argparse.ArgumentParser()
p.add_argument("--config", default="configs/demo.yaml")
p.add_argument("--root", default="runtime/demo")
a = p.parse_args()
c, root = config(a.config), Path(a.root)
quality_tags = {
    "unit_converted",
    "late",
    "negative_power",
    "status_power_conflict",
    "duplicate_conflict_or_exact",
    "power_physical_limit",
    "counter_reset_or_replacement",
    "counter_physical_limit",
    "weather_missing",
}
positive_mutations = set(CASES) - {
    "seconds",
    "milliseconds",
    "timezone_equivalent",
    "added_field",
    "sensor_stuck",
    "sensor_drift",
}
truth_records, counts, examples = [], [0, 0, 0], {"fp": [], "fn": []}
known_gap_expected, known_gap_missing = 0, 0
for folder in sorted((root / "raw").glob("date=*")):
    day = folder.name[5:]
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    delta = (pd.Timestamp(day) - pd.Timestamp(c["start"])).days
    labels = {}
    for inv in range(c.get("inverters", 1)):
        for station, samples, kind in [
            (3, [100], "unit"),
            (3, [102], "invalid_number"),
            (3, [112, 113], "duplicate"),
            (4, [110], "illegal_date"),
            (4, [111], "unknown_device"),
            (5, [90], "late"),
            (5, [95, 96], "counter_reset_and_rebound"),
        ]:
            if station < c["stations"]:
                for sample in samples:
                    labels[f"{day}-{station}-{inv}-{sample}"] = kind
        mutation = CASES[delta % len(CASES)]
        if c["stations"] > 6 and mutation in positive_mutations:
            labels[f"{day}-6-{inv}-115"] = mutation
            if mutation == "counter_reset":
                labels[f"{day}-6-{inv}-116"] = "counter_rebound"
    detected, observed_ids = set(), set()
    dwd = parquet_read(root / "dwd" / folder.name / "part.parquet")
    for r in dwd[["message_id", "quality_tags"]].itertuples(index=False):
        tags = set(r.quality_tags.split("|"))
        if tags & quality_tags:
            detected.add(r.message_id)
    quarantine = parquet_read(root / "quarantine" / folder.name / "part.parquet")
    quarantined_lines = set(quarantine.source_line)
    for n, line in enumerate((folder / "telemetry.jsonl").read_text(encoding="utf-8-sig").splitlines(), 1):
        try:
            m = json.loads(line)
            mid = m["message_id"]
            observed_ids.add(mid)
            expected = mid in labels
        except (ValueError, KeyError):
            mid, expected = f"parse-{day}-{n}", n == manifest["rows"]
        prediction = mid in detected or n in quarantined_lines
        if expected:
            truth_records.append(
                {"message_id": mid, "day": day, "source_line": n, "kind": labels.get(mid, "parse_error")}
            )
        tp, fp, fn = prediction and expected, prediction and not expected, not prediction and expected
        for j, v in enumerate([tp, fp, fn]):
            counts[j] += int(v)
        for key, flag in [("fp", fp), ("fn", fn)]:
            if flag and len(examples[key]) < 5:
                examples[key].append({"message_id": mid, "source_line": n, "day": day})
    if c["stations"] > 2:
        for inv in range(c.get("inverters", 1)):
            for sample in range(125, 140):
                known_gap_expected += 1
                known_gap_missing += f"{day}-2-{inv}-{sample}" not in observed_ids
json_write(root / "simulation_truth_quality" / "mutation_rows.json", truth_records)
result = {
    "synthetic": True,
    "scope": "known scheduled row corruptions; not all real-world data quality faults",
    "truth_source": "versioned injection schedule, independently enumerated here for post-hoc evaluation",
    "config_sha256": c["config_sha256"],
    "point_quality": classification(*counts),
    "scheduled_gap_samples": known_gap_expected,
    "scheduled_gap_samples_absent": known_gap_missing,
    "examples": examples,
    "limits": [
        "single-sample sensor_stuck is not observable",
        "sensor voltage drift is a fault candidate, not a quality label",
        "point scoring does not provide event-level quality matching",
        "random missing rows not used as labeled positives",
        "late backfill intentionally accepts late rows; compare same operating mode",
    ],
}
json_write(root / "quality_evaluation.json", result)
print(json.dumps(result, ensure_ascii=False, indent=2))

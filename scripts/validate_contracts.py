"""Enforce versioned schema, units, uniqueness and model feature contracts."""

import argparse
import json
from pathlib import Path

import yaml

from pv_pipeline.core import FEATURES, parquet_read

p = argparse.ArgumentParser()
p.add_argument("--root", default="runtime/smoke")
p.add_argument("--contracts", default="configs/contracts.yaml")
a = p.parse_args()
c = yaml.safe_load(Path(a.contracts).read_text(encoding="utf-8"))
root, checked = Path(a.root), 0
for layer in ["dwd", "dws", "scored"]:
    paths = sorted((root / layer).glob("date=*/part.parquet"))
    assert paths, f"Missing {layer}"
    contract = c[layer]
    for path in paths:
        df = parquet_read(path)
        assert set(contract["required"]) <= set(df.columns), str(path)
        assert not df.duplicated(contract["key"]).any(), f"Duplicate key {path}"
        for name, unit in contract.get("units", {}).items():
            assert (df[name] == unit).all(), f"Bad unit {path}/{name}"
        if layer == "dwd":
            assert (df.ac_kw.dropna() >= 0).all()
            assert (df.capacity_kwp > 0).all()
            assert not df.interpolated.any(), "This version explicitly disables interpolation"
        elif layer == "dws":
            assert (df.observed_kwh >= 0).all()
            assert df.daylight_coverage.dropna().between(0, 1).all()
            assert df.communication_online.between(0, 1).all()
        else:
            assert (df.predicted_kw.dropna() >= 0).all()
            unknown = df.predicted_kw.isna()
            assert df.loc[unknown, "quality_tags"].str.contains("weather_missing").all()
        checked += 1
manifest = json.loads((root / "models/manifest.json").read_text(encoding="utf-8"))
assert manifest["features"] == FEATURES
assert not set(FEATURES) & set(c["forbidden_model_features"])
assert manifest["truth_used"] is False
result = {
    "synthetic": True,
    "schema_version": c["schema_version"],
    "partitions_checked": checked,
    "units_and_keys": "passed",
    "model_feature_contract": "passed",
}
print(json.dumps(result, indent=2))

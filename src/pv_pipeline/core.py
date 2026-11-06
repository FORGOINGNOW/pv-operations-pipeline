"""Shared contracts. No simulation labels are available to transformation code."""

import hashlib
import json
import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import yaml

VERSION = "pv-v1"
FEATURES = [
    "poa_wm2",
    "ambient_c",
    "wind_ms",
    "capacity_kwp",
    "inverter_capacity_kw",
    "tilt_deg",
    "azimuth_deg",
    "gamma",
    "hour_sin",
    "hour_cos",
    "doy_sin",
    "doy_cos",
]


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def config(path):
    with open(path, encoding="utf-8-sig") as f:
        c = yaml.safe_load(f)
    if c["timezone"] != "Asia/Shanghai" or not 1 <= c["stations"] <= 100000:
        raise ValueError("Unsupported timezone or station count")
    if not 1 <= c.get("inverters", 1) <= 8:
        raise ValueError("inverters must be 1..8")
    if pd.Timestamp(c["start"]) >= pd.Timestamp(c["end"]):
        raise ValueError("start must precede exclusive end")
    c["config_sha256"] = digest(path)
    return c


def json_write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, default=str, allow_nan=False), encoding="utf-8"
    )
    os.replace(tmp, path)


def parquet_write(path, frame):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with duckdb.connect() as db:
        db.register("frame", frame)
        db.execute("COPY frame TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(tmp)])
    os.replace(tmp, path)


def parquet_read(path):
    with duckdb.connect() as db:
        return db.execute("SELECT * FROM read_parquet(?, union_by_name=true)", [str(path)]).df()


def read_layer(root, layer, dates=None):
    paths = sorted((Path(root) / layer).glob("date=*/part.parquet"))
    if dates is not None:
        wanted = set(dates)
        paths = [p for p in paths if p.parent.name[5:] in wanted]
    if not paths:
        return pd.DataFrame()
    with duckdb.connect() as db:
        return db.execute(
            "SELECT * EXCLUDE(date) FROM read_parquet(?, hive_partitioning=true, union_by_name=true)",
            [[str(p) for p in paths]],
        ).df()


def dates_between(start, end):
    return [d.strftime("%Y-%m-%d") for d in pd.date_range(start, end, inclusive="left", freq="D")]


def features(df):
    out = df.copy()
    ts = pd.to_datetime(out["event_time"], utc=True).dt.tz_convert("Asia/Shanghai")
    h = ts.dt.hour + ts.dt.minute / 60
    for name, val, cycle in [("hour", h, 24), ("doy", ts.dt.dayofyear, 365.25)]:
        out[name + "_sin"] = np.sin(2 * np.pi * val / cycle)
        out[name + "_cos"] = np.cos(2 * np.pi * val / cycle)
    return out


def physical(df):
    cell = df["ambient_c"] + df["poa_wm2"] * 0.028 / (1 + df["wind_ms"] * 0.08)
    dc = df["capacity_kwp"] * df["poa_wm2"].clip(lower=0) / 1000
    dc *= (1 + df["gamma"] * (cell - 25)).clip(0.5, 1.2)
    return np.minimum(dc * 0.94 * 0.965, df["inverter_capacity_kw"]).clip(lower=0)


def integrate(times, values, max_gap_minutes=10, day=None):
    """Trapezoids only between finite endpoints; split at local midnight, no extrapolation."""
    t = pd.DatetimeIndex(pd.to_datetime(times, utc=True)).as_unit("ns")
    p = np.asarray(values, dtype=float)
    order = np.argsort(t.asi8)
    t, p = t[order], p[order]
    if len(t) < 2:
        return 0.0, 0.0
    seconds = np.diff(t.asi8) / 1e9
    good = (seconds > 0) & (seconds <= max_gap_minutes * 60) & np.isfinite(p[:-1]) & np.isfinite(p[1:])
    energy = 0.0
    duration = 0.0
    left = pd.Timestamp(day, tz="Asia/Shanghai").tz_convert("UTC") if day else None
    right = left + pd.Timedelta(days=1) if day else None
    for i in np.flatnonzero(good):
        a, b = t[i], t[i + 1]
        lo, hi = (max(a, left), min(b, right)) if day else (a, b)
        if hi <= lo:
            continue
        f0, f1 = (lo - a).total_seconds() / seconds[i], (hi - a).total_seconds() / seconds[i]
        v0, v1 = p[i] + (p[i + 1] - p[i]) * f0, p[i] + (p[i + 1] - p[i]) * f1
        dt = (hi - lo).total_seconds() / 3600
        energy += (v0 + v1) * 0.5 * dt
        duration += dt
    return float(energy), float(duration)


def counter_delta(previous, current, capacity_kw, hours, rollover=None):
    if not np.isfinite([previous, current]).all() or hours <= 0:
        return None, "invalid"
    delta = current - previous
    reason = "ok"
    if delta < 0:
        if rollover is None:
            return None, "reset_or_replacement"
        delta, reason = current + rollover - previous, "rollover"
    if delta < 0 or delta > capacity_kw * hours * 1.2:
        return None, "physical_limit"
    return float(delta), reason

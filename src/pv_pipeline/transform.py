"""ODS -> DWD -> DWS; source lineage and multitag quality are preserved."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .core import digest, integrate, json_write, parquet_read, parquet_write


def collect(root, c, day, **_):
    folder = Path(root) / "raw" / f"date={day}"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    for name, checksum in manifest["sha256"].items():
        if digest(folder / name) != checksum:
            raise ValueError(f"Raw integrity failure: {name}")
    rows = []
    offset = 0
    with open(folder / "telemetry.jsonl", "rb") as f:
        for line_no, line in enumerate(f, 1):
            rows.append(
                dict(
                    source_file=f"raw/date={day}/telemetry.jsonl",
                    source_line=line_no,
                    source_byte=offset,
                    payload=line.decode("utf-8-sig", errors="replace").rstrip("\r\n"),
                )
            )
            offset += len(line)
    parquet_write(Path(root) / "ods" / f"date={day}" / "part.parquet", pd.DataFrame(rows))
    return {"input_count": len(rows), "output_count": len(rows)}


def parse_time(value):
    if isinstance(value, (int, float)):
        return pd.to_datetime(value, unit="ms" if abs(value) > 1e11 else "s", utc=True)
    t = pd.Timestamp(value)
    if t.tzinfo is None:
        raise ValueError("timezone_missing")
    return t.tz_convert("UTC")


def normalize(payload, c, day, allow_late=False):
    m = json.loads(payload)
    if m.get("schema_version") != "1.0":
        raise ValueError("schema_version")
    t, ingest = parse_time(m["event_time"]), parse_time(m["ingest_time"])
    if pd.isna(t) or pd.isna(ingest):
        raise ValueError("invalid_time")
    if t.tz_convert(c["timezone"]).strftime("%Y-%m-%d") != day:
        raise ValueError("wrong_partition_requires_backfill")
    if ingest < t - pd.Timedelta(minutes=5):
        raise ValueError("future_event_or_clock")
    if ingest - t > pd.Timedelta(days=c["lookback_days"]) and not allow_late:
        raise ValueError("late_beyond_window")
    flags = []
    if ingest - t > pd.Timedelta(minutes=30):
        flags.append("late")
    for name in ["ac_kw", "dc_kw", "cumulative_kwh", "voltage_a", "frequency_hz", "inverter_c"]:
        m[name] = float(m[name])
        if not np.isfinite(m[name]):
            raise ValueError("nonfinite_" + name)
    factor = {"kW": 1, "W": 0.001}.get(m["power_unit"])
    efactor = {"kWh": 1, "Wh": 0.001}.get(m["energy_unit"])
    if factor is None or efactor is None:
        raise ValueError("unknown_unit")
    if factor != 1 or efactor != 1:
        flags.append("unit_converted")
    m["ac_kw"] *= factor
    m["dc_kw"] *= factor
    m["cumulative_kwh"] *= efactor
    m["source_power_unit"], m["source_energy_unit"] = m["power_unit"], m["energy_unit"]
    m["power_unit"], m["energy_unit"] = "kW", "kWh"
    if m["ac_kw"] < 0:
        flags.append("negative_power")
        m["ac_kw"] = np.nan
    if m["voltage_a"] > 253 or m["voltage_a"] < 207:
        flags.append("grid_voltage_candidate")
    if abs(m["frequency_hz"] - 50) > 0.5:
        flags.append("grid_frequency_candidate")
    if m["status"] == "stopped" and m["ac_kw"] > 0.2:
        flags.append("status_power_conflict")
    m.update(event_time=t, ingest_time=ingest, quality_tags="|".join(flags), interpolated=False)
    return m


def clean(root, c, day, allow_late=False, **_):
    root = Path(root)
    source = parquet_read(root / "ods" / f"date={day}" / "part.parquet")
    archive = pd.read_csv(root / "raw" / f"date={day}" / "stations.csv")
    known = set(archive.station_id)
    rows, bad = [], []
    for r in source.to_dict("records"):
        try:
            m = normalize(r["payload"], c, day, allow_late)
            if m["station_id"] not in known or not m["inverter_id"].startswith(m["station_id"] + "-I"):
                raise ValueError("unknown_device")
            if int(m["inverter_id"].split("-I")[1]) >= c.get("inverters", 1):
                raise ValueError("unknown_inverter")
            m.update({k: r[k] for k in ["source_file", "source_line", "source_byte"]})
            rows.append(m)
        except (ValueError, KeyError, TypeError, OverflowError) as e:
            bad.append({**r, "reason": str(e)[:200]})
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("No valid telemetry; refuse successful partition")
    keys = ["inverter_id", "event_time"]
    duplicated = df.duplicated(keys, keep=False)
    df.loc[duplicated, "quality_tags"] += "|duplicate_conflict_or_exact"
    df = df.sort_values(keys + ["ingest_time", "sequence_no", "source_line"], kind="stable")
    before = len(df)
    df = df.drop_duplicates(keys, keep="last")
    duplicate_count = before - len(df)
    archive["valid_from"] = pd.to_datetime(archive.valid_from, utc=True)
    archive["valid_to"] = pd.to_datetime(archive.valid_to, utc=True)
    df = df.merge(archive, on="station_id", validate="many_to_one")
    expired = ~((df.event_time >= df.valid_from) & (df.event_time < df.valid_to))
    if expired.any():
        bad.extend(
            {
                "payload": "",
                "reason": "archive_expired",
                "source_file": r.source_file,
                "source_line": r.source_line,
                "source_byte": r.source_byte,
            }
            for r in df[expired].itertuples()
        )
        df = df[~expired].copy()
    df["capacity_kwp"] /= c.get("inverters", 1)
    df["inverter_capacity_kw"] /= c.get("inverters", 1)
    excessive = df.ac_kw > df.inverter_capacity_kw * 1.3
    df.loc[excessive, "quality_tags"] += "|power_physical_limit"
    df.loc[excessive, "ac_kw"] = np.nan
    ordered = df.sort_values(["inverter_id", "event_time"])
    delta = ordered.groupby("inverter_id").cumulative_kwh.diff()
    elapsed = ordered.groupby("inverter_id").event_time.diff().dt.total_seconds() / 3600
    reset = delta < 0
    limit = delta > ordered.inverter_capacity_kw * elapsed * 1.2
    df.loc[ordered.index[reset], "quality_tags"] += "|counter_reset_or_replacement"
    df.loc[ordered.index[limit], "quality_tags"] += "|counter_physical_limit"
    weather = pd.read_csv(root / "raw" / f"date={day}" / "weather.csv")
    weather["event_time"] = pd.to_datetime(weather.event_time, utc=True)
    df = df.merge(
        weather.drop(columns="timezone"), on=["station_id", "event_time"], how="left", validate="many_to_one"
    )
    df.loc[df.poa_wm2.isna(), "quality_tags"] += "|weather_missing"
    parquet_write(root / "dwd" / f"date={day}" / "part.parquet", df)
    columns = ["payload", "reason", "source_file", "source_line", "source_byte"]
    parquet_write(root / "quarantine" / f"date={day}" / "part.parquet", pd.DataFrame(bad, columns=columns))
    stats = {
        "input_count": len(source),
        "retained": len(df),
        "deduplicated": duplicate_count,
        "quarantined": len(bad),
        "filled": 0,
        "output_count": len(df),
        "missing_grid_rows": c["stations"] * c.get("inverters", 1) * 288 - len(df),
        "reconciliation_ok": len(source) == len(df) + duplicate_count + len(bad),
        "interpolation_policy": "disabled; unknown stays unknown",
    }
    if not stats["reconciliation_ok"]:
        raise AssertionError("Row conservation failed")
    json_write(root / "quality" / f"{day}.json", stats)
    return stats


def aggregate(root, c, day, **_):
    root = Path(root)
    df = parquet_read(root / "dwd" / f"date={day}" / "part.parquet")
    previous = (pd.Timestamp(day) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    path = root / "dwd" / f"date={previous}" / "part.parquet"
    # Previous endpoint permits boundary segment ownership by the CURRENT local day.
    # Here it ends at 00:00 so contributes zero; last 23:55->24:00 is unknown until next partition.
    rows = []
    for sid, station in df.groupby("station_id"):
        energy, valid_h, poa_energy = 0.0, 0.0, 0.0
        for _, inv in station.groupby("inverter_id"):
            inv = inv.sort_values("event_time")
            if path.exists():
                # No cross-partition extrapolation; daily partitions deliberately exclude trailing interval.
                pass
            e, hours = integrate(inv.event_time, inv.ac_kw, c["max_gap_minutes"], day)
            h, _ = integrate(inv.event_time, inv.poa_wm2 / 1000, c["max_gap_minutes"], day)
            energy += e
            valid_h += hours
            poa_energy += h / c.get("inverters", 1)
        capacity = station.capacity_kwp.iloc[0] * c.get("inverters", 1)
        n_inv = c.get("inverters", 1)
        # Weather grid defines expected daylight independent of telemetry gaps.
        weather = pd.read_csv(root / "raw" / f"date={day}" / "weather.csv")
        expected_day = int(((weather.station_id == sid) & (weather.poa_wm2 >= 50)).sum()) * n_inv
        day_valid = station[(station.poa_wm2 >= 50) & station.ac_kw.notna()]
        coverage = len(day_valid) / expected_day if expected_day else None
        online = len(station) / (288 * n_inv)
        available = float((day_valid.status == "running").mean()) if len(day_valid) else None
        confident = coverage is not None and coverage >= c["coverage_min"]
        rows.append(
            dict(
                station_id=sid,
                day=day,
                region=station.region.iloc[0],
                capacity_kwp=capacity,
                tilt_deg=float(station.tilt_deg.iloc[0]),
                azimuth_deg=float(station.azimuth_deg.iloc[0]),
                inverter_model=station.inverter_model.iloc[0],
                observed_kwh=energy,
                estimated_kwh=None,
                specific_yield=energy / capacity if confident else None,
                poa_kwh_m2=poa_energy,
                pr=energy / (capacity * poa_energy) if confident and poa_energy > 0.1 else None,
                daylight_coverage=coverage,
                communication_online=online,
                device_availability=available,
                availability_status="observed_only" if online < 1 else "complete",
                confidence="sufficient" if confident else "insufficient",
                valid_hours=valid_h / n_inv,
                energy_source="bounded_power_trapezoid",
                synthetic_revenue_yuan=energy * c["tariff_yuan_kwh"],
                maintenance=bool((station.status == "maintenance").any()),
                known_alarm=bool((station.alarm_code != "OK").any()),
            )
        )
    out = pd.DataFrame(rows)
    parquet_write(root / "dws" / f"date={day}" / "part.parquet", out)
    return {"input_count": len(df), "output_count": len(out)}

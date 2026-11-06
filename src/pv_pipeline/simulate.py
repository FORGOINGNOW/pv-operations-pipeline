"""Two stages: latent equipment process, then transport/measurement corruption.

Truth is written independently, never attached to telemetry or weather.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .core import digest, json_write, physical
from .quality import CASES, mutate

FAULTS = [
    "shading",
    "soiling",
    "snow",
    "degradation",
    "string_failure",
    "mppt_fault",
    "trip",
    "overtemperature",
    "efficiency_loss",
    "grid_outage",
    "overvoltage",
    "frequency",
    "curtailment",
    "planned_maintenance",
    "meter_bias",
    "sensor_bias",
]


def rng_for(c, day, station=0):
    return np.random.default_rng(np.random.SeedSequence([c["seed"], int(day.replace("-", "")), station]))


def stations(c):
    rows = []
    for i in range(c["stations"]):
        rows.append(
            dict(
                station_id=f"S{i:04d}",
                region=f"Fictional-{i // 12:02d}",
                latitude=30 + (i // 12) % 3,
                longitude=120 + (i // 12) % 2,
                capacity_kwp=5 + i % 4,
                inverter_capacity_kw=(5 + i % 4) * 0.85,
                tilt_deg=25 + (i // 6 % 2) * 5,
                azimuth_deg=180 + (i // 6 % 2) * 10,
                gamma=-0.0035,
                commissioned="2024-06-01",
                retired=None,
                valid_from="2024-01-01T00:00:00+08:00",
                valid_to="2030-01-01T00:00:00+08:00",
                module_model="Fiction-M400",
                inverter_model="Fiction-I8",
            )
        )
    return pd.DataFrame(rows)


def generate(root, c, day, **_):
    root = Path(root)
    folder = root / "raw" / f"date={day}"
    if (folder / "manifest.json").exists():
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        if manifest["config_sha256"] != c["config_sha256"]:
            raise ValueError("Raw is immutable: use a new runtime root for a changed configuration")
        if all(digest(folder / name) == checksum for name, checksum in manifest["sha256"].items()):
            return {"output_count": manifest["rows"], "reused": True}
        raise ValueError("Raw checksum mismatch")
    folder.mkdir(parents=True, exist_ok=True)
    archive = stations(c)
    archive.to_csv(folder / "stations.csv", index=False)
    t = pd.date_range(day, periods=288, freq="5min", tz=c["timezone"])
    hour = np.arange(288) / 12
    doy = t[0].dayofyear
    truth, weather, telemetry, events = [], [], [], []
    day_idx = (t[0].date() - pd.Timestamp(c["start"]).date()).days
    shared = {}
    for row in archive.to_dict("records"):
        i = int(row["station_id"][1:])
        rg = row["region"]
        if rg not in shared:
            r = rng_for(c, day, 100000 + i // 12)
            # Correlated clouds on a common regional weather process, not independent white noise.
            cloud = np.clip(np.repeat(r.uniform(0.25, 1, 24), 12), 0.1, 1)
            shared[rg] = np.convolve(np.pad(cloud, (6, 6), mode="edge"), np.ones(13) / 13, mode="valid")
        r = rng_for(c, day, i)
        lat, tilt = np.radians(row["latitude"]), np.radians(row["tilt_deg"])
        decl = np.radians(23.44 * np.sin(2 * np.pi * (284 + doy) / 365))
        ha = np.radians(15 * (hour - 12) + row["longitude"] - 120)
        sin_alt = np.sin(lat) * np.sin(decl) + np.cos(lat) * np.cos(decl) * np.cos(ha)
        az_offset = np.radians(row["azimuth_deg"] - 180)
        incidence = np.sin(decl) * np.sin(lat - tilt) + np.cos(decl) * np.cos(lat - tilt) * np.cos(ha)
        incidence *= np.cos(az_offset)
        dni = np.where(sin_alt > 0, 850 * shared[rg], 0)
        dhi = np.where(sin_alt > 0, 100 * np.clip(sin_alt, 0, 1), 0)
        ghi = dni * np.clip(sin_alt, 0, 1) + dhi
        poa = np.where(
            sin_alt > 0,
            dni * np.clip(incidence, 0, 1)
            + dhi * (1 + np.cos(tilt)) / 2
            + ghi * 0.2 * (1 - np.cos(tilt)) / 2,
            0,
        )
        poa *= r.uniform(0.98, 1.02)
        ambient = 17 + 12 * np.sin(2 * np.pi * (doy - 100) / 365) + 4 * np.sin(2 * np.pi * (hour - 8) / 24)
        wind = np.full(288, r.uniform(0.5, 5))
        base = pd.DataFrame({**row, "poa_wm2": poa, "ambient_c": ambient, "wind_ms": wind})
        latent = np.asarray(physical(base))
        observed = latent * np.clip(r.normal(1, 0.012, 288), 0.95, 1.05)
        status, code = np.full(288, "running", dtype=object), np.full(288, "OK", dtype=object)
        voltage, freq = np.full(288, 230.0), np.full(288, 50.0)
        # Sparse, rotating, deterministic intervals; baseline stations remain available.
        if i % 8 < 2 and day_idx % 7 < 3:
            kind = FAULTS[(day_idx // 7 + i) % len(FAULTS)]
            start, stop = (120, 168) if day_idx % 3 else (132, 135)
            mask = np.arange(288) >= start
            mask &= np.arange(288) < stop
            factor = 0.45
            if kind == "soiling":
                factor = 0.7
            if kind == "degradation":
                factor = 1 - 0.35 * doy / 365
                mask = poa > 0
            if kind in {"trip", "grid_outage", "planned_maintenance"}:
                factor = 0
                status[mask] = "maintenance" if kind == "planned_maintenance" else "stopped"
            if kind == "overvoltage":
                voltage[mask] = 265
            if kind == "frequency":
                freq[mask] = 52
            if kind == "sensor_bias":
                poa = poa.copy()
                poa[mask] *= 1.6
            else:
                observed[mask] *= factor
            code[mask] = "MAINT" if kind == "planned_maintenance" else "CHECK"
            indices = np.flatnonzero(mask)
            truth.append(
                dict(
                    truth_id=f"{day}-{i}-{kind}",
                    station_id=row["station_id"],
                    inverter_id=f"{row['station_id']}-I0",
                    kind=kind,
                    category="equipment",
                    start=str(t[indices[0]]),
                    end=str(t[indices[-1]] + pd.Timedelta(minutes=5)),
                    severity=1 - factor,
                    observable=kind != "planned_maintenance",
                    parameters={"factor": factor},
                    overlaps=[],
                )
            )
            events.append(f"{t[start].isoformat()}|{row['station_id']}|{status[start]}|inspection_candidate")
        for inv in range(c.get("inverters", 1)):
            n_inv = c.get("inverters", 1)
            p = observed / n_inv
            counter = 10000 + day_idx * 30 / n_inv + np.cumsum(p) / 12
            for k in range(288):
                msg = dict(
                    schema_version="1.0",
                    source_system="fictional-inverter",
                    message_id=f"{day}-{i}-{inv}-{k}",
                    event_time=t[k].isoformat(),
                    ingest_time=(t[k] + pd.Timedelta(seconds=15)).isoformat(),
                    station_id=row["station_id"],
                    inverter_id=f"{row['station_id']}-I{inv}",
                    sequence_no=k,
                    ac_kw=round(float(p[k]), 6),
                    dc_kw=round(float(p[k] / 0.965), 6),
                    cumulative_kwh=round(float(counter[k]), 6),
                    power_unit="kW",
                    energy_unit="kWh",
                    voltage_a=voltage[k],
                    voltage_b=voltage[k],
                    voltage_c=voltage[k],
                    current_a=round(float(p[k] * 1000 / 690), 4),
                    current_b=round(float(p[k] * 1000 / 690), 4),
                    current_c=round(float(p[k] * 1000 / 690), 4),
                    frequency_hz=freq[k],
                    power_factor=0.99,
                    mppt_v=380,
                    mppt_a=round(float(p[k] / 0.965 * 1000 / 380), 4),
                    inverter_c=round(float(ambient[k] + poa[k] * 0.035), 2),
                    module_c=round(float(ambient[k] + poa[k] * 0.028), 2),
                    status=status[k],
                    alarm_code=code[k],
                    firmware="fiction-1.0",
                    latency_s=15,
                )
                # Stage 2: observation faults independent of latent process.
                if i == 2 and 125 <= k < 140:
                    continue
                if i == 3 and k == 100:
                    msg["power_unit"], msg["ac_kw"] = "W", msg["ac_kw"] * 1000
                if i == 3 and k == 101:
                    msg["event_time"] = int(t[k].timestamp() * 1000)
                if i == 3 and k == 102:
                    msg["ac_kw"] = "invalid"
                if i == 4 and k == 110:
                    msg["event_time"] = "2025-02-30"
                if i == 4 and k == 111:
                    msg["station_id"] = "UNKNOWN"
                if i == 5 and k == 90:
                    msg["ingest_time"] = (t[k] + pd.Timedelta(days=5)).isoformat()
                if i == 5 and k == 95:
                    msg["cumulative_kwh"] = 0
                if r.random() < 0.001:
                    continue
                if i == 6 and k == 115:
                    msg = mutate(msg, CASES[day_idx % len(CASES)])
                telemetry.append(msg)
                if i == 3 and k in {112, 113}:
                    duplicate = msg.copy()
                    if k == 113:
                        duplicate["ac_kw"] *= 1.1
                        duplicate["ingest_time"] = (t[k] + pd.Timedelta(seconds=30)).isoformat()
                    telemetry.append(duplicate)
        for k in range(288):
            weather.append(
                dict(
                    station_id=row["station_id"],
                    event_time=t[k].isoformat(),
                    ghi_wm2=round(float(ghi[k]), 4),
                    dni_wm2=round(float(dni[k]), 4),
                    dhi_wm2=round(float(dhi[k]), 4),
                    poa_wm2=round(float(poa[k]), 4),
                    ambient_c=round(float(ambient[k]), 3),
                    wind_ms=round(float(wind[k]), 3),
                    rain_mm=1.0 if shared[rg][k] < 0.3 else 0,
                    weather_type="cloudy" if shared[rg][k] < 0.7 else "clear",
                    weather_quality="simulated_sensor",
                    timezone=c["timezone"],
                )
            )
    rng_for(c, day).shuffle(telemetry)
    with open(folder / "telemetry.jsonl", "w", encoding="utf-8") as f:
        f.writelines(json.dumps(m, separators=(",", ":")) + "\n" for m in telemetry)
        f.write('{"truncated":\n')
    pd.DataFrame(weather).to_csv(folder / "weather.csv", index=False)
    (folder / "events.log").write_text("\n".join(events) + "\n", encoding="utf-8")
    json_write(root / "simulation_truth" / f"{day}.json", truth)
    checksums = {p.name: digest(p) for p in folder.iterdir() if p.name != "manifest.json"}
    json_write(
        folder / "manifest.json",
        {
            "config_sha256": c["config_sha256"],
            "data_version": c["data_version"],
            "date": day,
            "rows": len(telemetry) + 1,
            "sha256": checksums,
            "grid_rows": c["stations"] * c.get("inverters", 1) * 288,
            "start": str(t[0]),
            "end_exclusive": str(t[0] + pd.Timedelta(days=1)),
        },
    )
    return {"output_count": len(telemetry) + 1}

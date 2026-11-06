"""Transport mutation fixtures. Mutations never expose their names in telemetry."""

import pandas as pd

CASES = [
    "seconds",
    "milliseconds",
    "timezone_equivalent",
    "clock_drift",
    "illegal_date",
    "cross_day",
    "future_clock",
    "irregular",
    "empty",
    "null",
    "nan",
    "inf",
    "invalid_number",
    "missing_field",
    "added_field",
    "renamed_field",
    "watts",
    "watt_hours",
    "negative",
    "spike",
    "counter_reset",
    "unknown_id",
    "unknown_inverter",
    "status_conflict",
    "sensor_stuck",
    "sensor_drift",
    "late_retransmit",
]


def mutate(message, case):
    m = message.copy()
    t = pd.Timestamp(m["event_time"])
    if case == "seconds":
        m["event_time"] = int(t.timestamp())
    elif case == "milliseconds":
        m["event_time"] = int(t.timestamp() * 1000)
    elif case == "timezone_equivalent":
        m["event_time"] = t.tz_convert("UTC").isoformat()
    elif case == "clock_drift":
        m["event_time"] = (t + pd.Timedelta(minutes=8)).isoformat()
    elif case == "illegal_date":
        m["event_time"] = "2025-02-30"
    elif case == "cross_day":
        m["event_time"] = (t + pd.Timedelta(days=1)).isoformat()
    elif case == "future_clock":
        m["event_time"] = (t + pd.Timedelta(hours=1)).isoformat()
    elif case == "irregular":
        m["event_time"] = (t + pd.Timedelta(seconds=30)).isoformat()
    elif case in {"empty", "null", "nan", "inf", "invalid_number"}:
        m["ac_kw"] = {"empty": "", "null": None, "nan": "NaN", "inf": "Inf", "invalid_number": "oops"}[case]
    elif case == "missing_field":
        m.pop("ac_kw")
    elif case == "added_field":
        m["new_vendor_note"] = "<script>not executable in dashboard</script>"
    elif case == "renamed_field":
        m["active_power"] = m.pop("ac_kw")
    elif case == "watts":
        m["ac_kw"], m["dc_kw"], m["power_unit"] = m["ac_kw"] * 1000, m["dc_kw"] * 1000, "W"
    elif case == "watt_hours":
        m["cumulative_kwh"], m["energy_unit"] = m["cumulative_kwh"] * 1000, "Wh"
    elif case == "negative":
        m["ac_kw"] = -1
    elif case == "spike":
        m["ac_kw"] = 1000
    elif case == "counter_reset":
        m["cumulative_kwh"] = 0
    elif case == "unknown_id":
        m["station_id"] = "UNMAPPED"
    elif case == "unknown_inverter":
        m["inverter_id"] = m.get("station_id", "S0000") + "-I99"
    elif case == "status_conflict":
        m["status"], m["ac_kw"] = "stopped", 2
    elif case == "sensor_stuck":
        m["voltage_a"] = 230
    elif case == "sensor_drift":
        m["voltage_a"] += 30
    elif case == "late_retransmit":
        m["ingest_time"] = (t + pd.Timedelta(days=5)).isoformat()
    else:
        raise ValueError(case)
    return m

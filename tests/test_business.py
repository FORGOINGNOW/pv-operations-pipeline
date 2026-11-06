import inspect
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pv_pipeline import analytics, transform
from pv_pipeline.analytics import classification, episodes, event_match, peer_deviation
from pv_pipeline.core import config, counter_delta, digest, integrate, parquet_read, physical
from pv_pipeline.simulate import generate
from pv_pipeline.transform import clean, collect, normalize


@pytest.fixture
def cfg():
    return config(Path(__file__).parents[1] / "configs/smoke.yaml")


def message(**updates):
    m = dict(
        schema_version="1.0",
        event_time="2025-01-01T12:00:00+08:00",
        ingest_time="2025-01-01T12:00:15+08:00",
        ac_kw=2,
        dc_kw=2.1,
        cumulative_kwh=10,
        voltage_a=230,
        frequency_hz=50,
        inverter_c=30,
        power_unit="kW",
        energy_unit="kWh",
        status="running",
    )
    return json.dumps({**m, **updates})


def test_T01_irregular_integration():
    t = ["2025-01-01T12:00+08:00", "2025-01-01T12:07+08:00", "2025-01-01T12:10+08:00"]
    assert integrate(t, [2, 2, 2])[0] == pytest.approx(1 / 3)
    assert integrate(t, [2, np.nan, 2])[0] == 0


def test_T02_midnight_and_gap():
    t = ["2025-01-01T23:55+08:00", "2025-01-02T00:05+08:00"]
    assert integrate(t, [2, 2], day="2025-01-01")[0] == pytest.approx(1 / 6)
    assert integrate(t, [2, 2], day="2025-01-02")[0] == pytest.approx(1 / 6)
    assert integrate([t[0], "2025-01-02T01:05+08:00"], [2, 2])[0] == 0


def test_T15_duckdb_microsecond_resolution():
    times = pd.date_range("2025-01-01", periods=3, freq="5min", tz="UTC").as_unit("us")
    assert integrate(times, [2, 1, 0])[0] == pytest.approx(1 / 6)
    assert integrate(times, [2, 1, 0])[0] >= 0


def test_T03_counter():
    assert counter_delta(100, 0, 5, 1)[0] is None
    assert counter_delta(999, 1, 5, 1, 1000) == (2, "rollover")
    assert counter_delta(0, 100, 5, 1)[1] == "physical_limit"


@pytest.mark.parametrize("timestamp", [1735704000, 1735704000000, "2025-01-01T04:00:00Z"])
def test_T04_timestamp_and_units(cfg, timestamp):
    m = normalize(message(event_time=timestamp, ac_kw=2000, power_unit="W"), cfg, "2025-01-01")
    assert m["ac_kw"] == 2
    assert m["power_unit"] == "kW"
    assert "unit_converted" in m["quality_tags"]


@pytest.mark.parametrize(
    "updates",
    [
        {"event_time": "bad"},
        {"event_time": "2025-01-01"},
        {"ac_kw": "NaN"},
        {"ac_kw": "Inf"},
        {"ac_kw": ""},
        {"power_unit": "MW"},
        {"schema_version": "99"},
    ],
)
def test_T05_quarantine(cfg, updates):
    with pytest.raises((ValueError, KeyError)):
        normalize(message(**updates), cfg, "2025-01-01")


def test_T06_late_and_fault_observation(cfg):
    with pytest.raises(ValueError, match="late_beyond"):
        normalize(message(ingest_time="2025-01-06T12:00+08:00"), cfg, "2025-01-01")
    assert (
        "late"
        in normalize(message(ingest_time="2025-01-06T12:00+08:00"), cfg, "2025-01-01", True)["quality_tags"]
    )
    assert normalize(message(voltage_a=270), cfg, "2025-01-01")["ac_kw"] == 2


def test_T07_end_to_end_quality_reproducibility(tmp_path, cfg):
    day = "2025-01-01"
    generate(tmp_path, cfg, day)
    raw = tmp_path / "raw" / f"date={day}" / "telemetry.jsonl"
    checksum = digest(raw)
    generate(tmp_path, cfg, day)
    assert digest(raw) == checksum
    collect(tmp_path, cfg, day)
    stats = clean(tmp_path, cfg, day)
    assert stats["reconciliation_ok"]
    assert stats["deduplicated"] == 2
    assert stats["quarantined"] >= 5
    df = parquet_read(tmp_path / "dwd" / f"date={day}" / "part.parquet")
    assert not df.duplicated(["inverter_id", "event_time"]).any()
    # No truth file is needed by any transformation.
    (tmp_path / "simulation_truth" / f"{day}.json").unlink()
    assert clean(tmp_path, cfg, day)["reconciliation_ok"]
    assert (df[df.poa_wm2 == 0].ac_kw == 0).all()
    assert df.poa_wm2.max() > 100


def test_T08_peers():
    assert peer_deviation(1, [1, 1, 1])[1] == "insufficient_peers"
    assert peer_deviation(0.4, [0.5] * 5)[0] == pytest.approx(-0.2)
    assert peer_deviation(0, [0] * 5)[1] == "small_denominator"
    assert peer_deviation(0.2, [0.2] * 5)[0] == 0  # common-mode cloudy weather


def test_T09_duration_gap_hysteresis():
    t = pd.date_range("2025-01-01", periods=9, freq="5min", tz="UTC")
    assert len(episodes(t, [True] * 7 + [False] * 2)) == 1
    assert not episodes(t[:6], [True] * 6)  # six samples span only 25min
    gaps = [t[0], t[1], t[2], t[6], t[7], t[8]]
    assert not episodes(gaps, [True] * 6)
    assert len(episodes(t, [True, True, True, False, True, True, True, False, False])) == 1


def test_T10_no_truth_dependency():
    assert "simulation_truth" not in inspect.getsource(transform)
    for f in [analytics.train, analytics.score, analytics.make_features]:
        assert "simulation_truth" not in inspect.getsource(f)
    assert "early_stopping=False" in inspect.getsource(analytics.train)
    assert "month <= 8" in inspect.getsource(analytics.train)
    assert "range(1, 29)" in inspect.getsource(analytics.score)


def test_T11_one_to_one_and_na():
    event = {"inverter_id": "I", "start": "2025-01-01T12:00Z", "end": "2025-01-01T13:00Z"}
    assert len(event_match([event, event], [event])) == 1
    assert classification(0, 0, 0)["precision"] is None


def test_T12_physics_clipping_and_night():
    df = pd.DataFrame(
        {
            "ambient_c": [20, 20],
            "poa_wm2": [0, 2000],
            "wind_ms": [1, 1],
            "capacity_kwp": [8, 8],
            "gamma": [-0.0035, -0.0035],
            "inverter_capacity_kw": [5, 5],
        }
    )
    assert list(physical(df)) == [0, 5]


def test_T13_multi_inverter_no_double_count(tmp_path, cfg):
    cfg = {**cfg, "inverters": 2}
    generate(tmp_path, cfg, "2025-01-01")
    collect(tmp_path, cfg, "2025-01-01")
    clean(tmp_path, cfg, "2025-01-01")
    df = parquet_read(tmp_path / "dwd/date=2025-01-01/part.parquet")
    assert df[df.station_id == "S0000"].capacity_kwp.unique().tolist() == [2.5]
    assert df[df.station_id == "S0000"].inverter_id.nunique() == 2


def test_T14_archive_expiry(tmp_path, cfg):
    generate(tmp_path, cfg, "2025-01-01")
    collect(tmp_path, cfg, "2025-01-01")
    p = tmp_path / "raw/date=2025-01-01/stations.csv"
    a = pd.read_csv(p)
    a.loc[0, "valid_to"] = "2024-12-31T00:00:00+08:00"
    a.to_csv(p, index=False)
    stats = clean(tmp_path, cfg, "2025-01-01")
    assert stats["reconciliation_ok"]
    q = parquet_read(tmp_path / "quarantine/date=2025-01-01/part.parquet")
    assert (q.reason == "archive_expired").any()

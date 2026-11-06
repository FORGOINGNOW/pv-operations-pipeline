import json

import pytest

from pv_pipeline.core import config
from pv_pipeline.quality import CASES, mutate
from pv_pipeline.transform import normalize


@pytest.mark.parametrize("case", CASES)
def test_T16_mutation_contract(case):
    from test_business import message

    m = json.loads(message())
    m.update(station_id="S0006", inverter_id="S0006-I0")
    corrupted = mutate(m, case)
    rejects = {
        "clock_drift",
        "illegal_date",
        "cross_day",
        "future_clock",
        "empty",
        "null",
        "nan",
        "inf",
        "invalid_number",
        "missing_field",
        "renamed_field",
        "late_retransmit",
    }
    c = config("configs/smoke.yaml")
    if case in rejects:
        with pytest.raises((ValueError, KeyError, TypeError)):
            normalize(json.dumps(corrupted), c, "2025-01-01")
    else:
        out = normalize(json.dumps(corrupted), c, "2025-01-01")
        assert out["event_time"].tzinfo is not None
        if case in {"watts", "watt_hours", "milliseconds", "seconds", "timezone_equivalent"}:
            assert out["ac_kw"] == 2
        if case == "negative":
            assert "negative_power" in out["quality_tags"]
        if case == "status_conflict":
            assert "status_power_conflict" in out["quality_tags"]

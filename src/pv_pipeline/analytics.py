"""Contemporaneous-weather power benchmarks; no day-ahead forecast claims."""

import json
import pickle
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from .core import FEATURES, VERSION, features, json_write, parquet_read, parquet_write, physical


def make_features(root, c, day, **_):
    df = parquet_read(Path(root) / "dwd" / f"date={day}" / "part.parquet")
    df = features(df)
    df["physical_kw"] = physical(df)
    parquet_write(Path(root) / "features" / f"date={day}" / "part.parquet", df)
    return {"input_count": len(df), "output_count": len(df)}


def model_sample(root):
    paths = [str(p) for p in sorted((Path(root) / "features").glob("date=*/part.parquet"))]
    cols = list(
        dict.fromkeys(
            FEATURES
            + [
                "event_time",
                "station_id",
                "ac_kw",
                "status",
                "alarm_code",
                "quality_tags",
                "weather_type",
                "physical_kw",
            ]
        )
    )
    # Stable hash sampling: bounded fitting/evaluation memory even for full profile.
    with duckdb.connect() as db:
        return db.execute(
            f"SELECT {','.join(cols)} FROM read_parquet(?, hive_partitioning=false) "
            "WHERE poa_wm2 >= 50 AND ac_kw IS NOT NULL "
            "ORDER BY hash(station_id, event_time) LIMIT 120000",
            [paths],
        ).df()


def metrics(y, p, capacity):
    valid = np.isfinite(y) & np.isfinite(p)
    if not valid.any():
        return {"n": 0, "mae_kw": None, "rmse_kw": None, "capacity_nmae": None}
    return {
        "n": int(valid.sum()),
        "mae_kw": float(mean_absolute_error(y[valid], p[valid])),
        "rmse_kw": float(np.sqrt(mean_squared_error(y[valid], p[valid]))),
        "capacity_nmae": float(np.mean(np.abs(y[valid] - p[valid]) / capacity[valid])),
    }


def train(root, c, *_args, **_):
    root = Path(root)
    df = model_sample(root)
    month = pd.to_datetime(df.event_time, utc=True).dt.tz_convert(c["timezone"]).dt.month
    quality = (df.quality_tags == "") & (df.status == "running") & (df.alarm_code == "OK")
    training = df[(month <= 8) & quality].copy()
    val = df[(month >= 9) & (month <= 10)].copy()
    # Smoke has no validation months: explicit baseline fallback, no invented validation.
    if len(training) < 20:
        raise ValueError("Insufficient training rows")
    trials = []
    best, best_score = None, np.inf
    for leaves in [7, 15]:
        model = HistGradientBoostingRegressor(
            max_iter=60,
            max_leaf_nodes=leaves,
            random_state=c["seed"],
            early_stopping=False,
            l2_regularization=1.0,
        )
        model.fit(training[FEATURES], training.ac_kw)
        error = mean_absolute_error(val.ac_kw, model.predict(val[FEATURES])) if len(val) else float(leaves)
        trials.append({"max_leaf_nodes": leaves, "validation_mae_kw": float(error) if len(val) else None})
        if error < best_score:
            best, best_score = model, error
    root.joinpath("models").mkdir(exist_ok=True)
    with open(root / "models" / "regressor.pkl.tmp", "wb") as f:
        pickle.dump(best, f)
    (root / "models" / "regressor.pkl.tmp").replace(root / "models" / "regressor.pkl")
    simple = float((training.ac_kw / training.capacity_kwp).median())
    meta = {
        "model_version": VERSION,
        "features": FEATURES,
        "config_sha256": c["config_sha256"],
        "target": "5-minute sampled mean AC kW; contemporaneous measured-style weather benchmark",
        "train_latest": str(training.event_time.max()),
        "train_n": len(training),
        "validation_n": len(val),
        "simple_capacity_coefficient": simple,
        "trials": trials,
        "truth_used": False,
        "sample_limit": 120000,
        "filter": "available status, alarm code and quality only; residual unlabeled contamination possible",
    }
    json_write(root / "models" / "manifest.json", meta)
    # Expanding-origin backtest; held-out months always later than fitting months.
    rolling = []
    for end_month, test_month in [(4, 5), (6, 7), (8, 9)]:
        tr, te = df[(month <= end_month) & quality], df[month == test_month]
        if len(tr) >= 20 and len(te):
            m = HistGradientBoostingRegressor(
                max_iter=40, max_leaf_nodes=7, early_stopping=False, random_state=c["seed"]
            ).fit(tr[FEATURES], tr.ac_kw)
            rolling.append(
                {
                    "train_through_month": end_month,
                    "test_month": test_month,
                    **metrics(te.ac_kw.to_numpy(), m.predict(te[FEATURES]), te.capacity_kwp.to_numpy()),
                }
            )
    json_write(root / "models" / "rolling_backtest.json", rolling)
    return {"input_count": len(df), "output_count": len(training)}


def peer_deviation(target, peers, minimum=5):
    peers = np.asarray(peers, dtype=float)
    peers = peers[np.isfinite(peers)]
    if len(peers) < minimum:
        return None, "insufficient_peers"
    baseline = float(np.median(peers))
    if baseline <= 0.02:
        return None, "small_denominator"
    return (float(target) - baseline) / baseline, "ok"


def episodes(times, bad, recovery=2, minimum_minutes=30, max_gap_minutes=10):
    """True elapsed time; gaps cut episodes. Recovery hysteresis needs 2 normal samples."""
    t = pd.DatetimeIndex(pd.to_datetime(times, utc=True))
    result, start, last_bad, normal = [], None, None, 0

    def close():
        if start is not None and (last_bad - start).total_seconds() / 60 >= minimum_minutes:
            result.append((start, last_bad))

    for i, flag in enumerate(bad):
        if i and (t[i] - t[i - 1]).total_seconds() > max_gap_minutes * 60:
            close()
            start, last_bad, normal = None, None, 0
        if flag:
            start = t[i] if start is None else start
            last_bad, normal = t[i], 0
        elif start is not None:
            normal += 1
            if normal >= recovery:
                close()
                start, last_bad, normal = None, None, 0
    close()
    return result


def score(root, c, day, **_):
    root = Path(root)
    df = parquet_read(root / "features" / f"date={day}" / "part.parquet")
    with open(root / "models" / "regressor.pkl", "rb") as f:
        model = pickle.load(f)  # Only load local generated artifact, never untrusted pickles.
    meta = json.loads((root / "models" / "manifest.json").read_text())
    pred = np.minimum(np.maximum(model.predict(df[FEATURES]), 0), df.inverter_capacity_kw)
    # Historical dates preceding model availability use the unfitted physics benchmark.
    earlier = df.event_time <= pd.Timestamp(meta["train_latest"])
    pred[earlier] = df.loc[earlier, "physical_kw"]
    df["prediction_source"] = np.where(earlier, "physical_pre_model_availability", "regression")
    pred[df.poa_wm2 < 5] = 0
    df["predicted_kw"] = pred
    df["residual_kw"] = df.ac_kw - pred
    df["physical_deviation"] = np.where(df.physical_kw > 0.1, df.ac_kw / df.physical_kw - 1, np.nan)
    df["peer_deviation"] = np.nan
    df["peer_status"] = "gated"
    # Match instantaneous weather, orientation, model; exclude target and observable alarms.
    df["normalized_power"] = df.ac_kw / df.capacity_kwp
    eligible = (
        (df.poa_wm2 >= 100) & (df.quality_tags == "") & (df.alarm_code == "OK") & (df.status == "running")
    )
    for _, ids in df.groupby(
        ["event_time", "region", "tilt_deg", "azimuth_deg", "inverter_model"]
    ).groups.items():
        g = df.loc[ids]
        irradiance = g.poa_wm2.to_numpy()
        power = g.normalized_power.to_numpy()
        stations = g.station_id.to_numpy()
        ok = eligible.loc[ids].to_numpy()
        deviations, statuses = [], []
        for j in range(len(g)):
            mask = ok & (stations != stations[j])
            mask &= np.abs(irradiance / max(irradiance[j], 1) - 1) < 0.15
            if irradiance[j] < 100 or not np.isfinite(power[j]):
                d, status = None, "gated"
            else:
                d, status = peer_deviation(power[j], power[mask], c["peer_min"])
            deviations.append(np.nan if d is None else float(d))
            statuses.append(status)
        df.loc[ids, "peer_deviation"] = deviations
        df.loc[ids, "peer_status"] = statuses
    # Self baseline only prior 28 calendar days, never full-year average or future scored rows.
    history = []
    for delta in range(1, 29):
        past = (pd.Timestamp(day) - pd.Timedelta(days=delta)).strftime("%Y-%m-%d")
        p = root / "dws" / f"date={past}" / "part.parquet"
        if p.exists():
            history.append(parquet_read(p))
    h = pd.concat(history, ignore_index=True) if history else pd.DataFrame()
    daily = parquet_read(root / "dws" / f"date={day}" / "part.parquet")
    daily["self_deviation"] = np.nan
    daily["self_status"] = "insufficient_healthy_history"
    if len(h):
        for ix, r in daily.iterrows():
            prev = h[
                (h.station_id == r.station_id)
                & ~h.maintenance
                & ~h.known_alarm
                & (h.confidence == "sufficient")
                & h.pr.between(0.6, 1.1)
            ]
            if len(prev) >= 5 and pd.notna(r.pr):
                baseline = prev.pr.median()
                daily.loc[ix, "self_deviation"] = r.pr / baseline - 1
                daily.loc[ix, "self_status"] = "ok"
    daily["peer_deviation"] = daily.station_id.map(df.groupby("station_id").peer_deviation.median())
    # Historical normalized PR EWMA: trend demo, not a causal degradation estimate.
    daily["ewma_pr"] = np.nan
    if len(h):
        for ix, r in daily.iterrows():
            prev = h[(h.station_id == r.station_id) & (h.confidence == "sufficient")].sort_values("day")
            if len(prev) >= 5:
                daily.loc[ix, "ewma_pr"] = prev.pr.ewm(alpha=0.2, adjust=False).mean().iloc[-1]
    daily["predicted_kwh"] = 0.0
    from .core import integrate

    for sid, g in df.groupby("station_id"):
        e = sum(
            integrate(inv.event_time, inv.predicted_kw, c["max_gap_minutes"], day)[0]
            for _, inv in g.groupby("inverter_id")
        )
        daily.loc[daily.station_id == sid, "predicted_kwh"] = e
    daily["suspected_loss_kwh"] = (daily.predicted_kwh - daily.observed_kwh).clip(lower=0)
    events = []
    cutoff = pd.Timestamp(meta["train_latest"])
    df["evaluation_eligible"] = df.event_time > cutoff
    for iid, g in df.sort_values("event_time").groupby("inverter_id"):
        gated = (
            (g.poa_wm2 >= 100)
            & g.ac_kw.notna()
            & ~g.quality_tags.str.contains("physical_limit|negative")
            & (g.status != "maintenance")
        )
        bad = gated & (g.physical_deviation < c["threshold"])
        df.loc[g.index, "rule_flag"] = bad
        df.loc[g.index, "fixed_flag"] = (g.ac_kw < 0.5) & (g.poa_wm2 >= 100)
        for start, end in episodes(g.event_time, bad, minimum_minutes=c["duration_minutes"]):
            interval = g[g.event_time.between(start, end)]
            events.append(
                dict(
                    event_id=f"{iid}-{start.isoformat()}",
                    station_id=g.station_id.iloc[0],
                    inverter_id=iid,
                    start=start.isoformat(),
                    end=end.isoformat(),
                    rule_version=VERSION,
                    rule="physical_residual_persistence",
                    severity="review",
                    confidence="candidate",
                    evidence={
                        "physical_deviation_median": float(interval.physical_deviation.median()),
                        "peer_deviation_median": float(interval.peer_deviation.median())
                        if interval.peer_deviation.notna().any()
                        else None,
                        "poa_wm2_median": float(interval.poa_wm2.median()),
                    },
                    candidates=["遮挡/积灰/限发/设备异常", "气象或计量偏差"],
                    action="人工核验运行日志、气象与设备档案；电气风险转专业人员",
                    evaluation_eligible=bool(start > cutoff),
                )
            )
    parquet_write(root / "scored" / f"date={day}" / "part.parquet", df)
    parquet_write(root / "ads" / f"date={day}" / "part.parquet", daily)
    json_write(root / "alerts" / f"{day}.json", events)
    return {"input_count": len(df), "output_count": len(events)}


def workorders(root):
    """Replay-derived state machine: deterministic IDs, merge, close, reopen; local outbox only."""
    root = Path(root)
    state, transitions = {}, []
    for path in sorted((root / "alerts").glob("*.json")):
        events = json.loads(path.read_text(encoding="utf-8"))
        active = set()
        for e in events:
            key = e["inverter_id"] + ":" + e["rule"]
            active.add(key)
            old = state.get(key)
            if old is None:
                state[key] = {
                    "workorder_id": key,
                    "status": "待核验",
                    "created": e["start"],
                    "assigned": None,
                    "processing": None,
                    "closed": None,
                    "reopens": 0,
                }
                transitions.append({"id": key, "at": e["start"], "to": "待核验"})
            elif old["status"] == "已关闭":
                old["status"], old["reopens"] = "复核", old["reopens"] + 1
                transitions.append({"id": key, "at": e["start"], "to": "复核"})
            state[key]["last_event"] = e
        for key, wo in state.items():
            if key not in active and wo["status"] != "已关闭":
                # Simulated dispatch/processing/closure, no external action.
                for label, field in [("已派单", "assigned"), ("处理中", "processing"), ("已关闭", "closed")]:
                    wo["status"], wo[field] = label, path.stem
                    transitions.append({"id": key, "at": path.stem, "to": label})
    json_write(
        root / "outbox" / "workorders.json",
        {"synthetic": True, "orders": list(state.values()), "transitions": transitions},
    )
    return state


def event_match(predictions, truths, tolerance_minutes=10):
    pairs, used = [], set()
    for pi, p in enumerate(predictions):
        candidates = []
        for ti, t in enumerate(truths):
            if ti in used or p["inverter_id"] != t["inverter_id"]:
                continue
            ps, pe, ts, te = [pd.Timestamp(v) for v in [p["start"], p["end"], t["start"], t["end"]]]
            tol = pd.Timedelta(minutes=tolerance_minutes)
            if ps <= te + tol and pe >= ts - tol:
                candidates.append((abs((ps - ts).total_seconds()), ti))
        if candidates:
            _, ti = min(candidates)
            used.add(ti)
            pairs.append((pi, ti))
    return pairs


def classification(tp, fp, fn):
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
    }


def evaluate(root, c, *_args, **_):
    """The ONLY consumer of simulation_truth outside generator and tests."""
    root = Path(root)
    df = model_sample(root)
    month = pd.to_datetime(df.event_time, utc=True).dt.tz_convert(c["timezone"]).dt.month
    test = df[month >= 11].copy()
    with open(root / "models" / "regressor.pkl", "rb") as f:
        model = pickle.load(f)
    meta = json.loads((root / "models" / "manifest.json").read_text())
    comparison = {}
    for name, pred in [
        ("physical", test.physical_kw.to_numpy()),
        (
            "regression",
            np.clip(model.predict(test[FEATURES]), 0, test.inverter_capacity_kw)
            if len(test)
            else np.array([]),
        ),
        ("capacity_median", test.capacity_kwp.to_numpy() * meta["simple_capacity_coefficient"]),
    ]:
        comparison[name] = metrics(test.ac_kw.to_numpy(), pred, test.capacity_kwp.to_numpy())
    strata = []
    for key in ["station_id", "weather_type", "inverter_capacity_kw"]:
        for label, g in test.groupby(key):
            strata.append(
                {
                    "dimension": key,
                    "value": str(label),
                    **metrics(g.ac_kw.to_numpy(), model.predict(g[FEATURES]), g.capacity_kwp.to_numpy()),
                }
            )
    all_events, all_truth = [], []
    for path in sorted((root / "alerts").glob("*.json")):
        all_events.extend(json.loads(path.read_text(encoding="utf-8")))
    for path in sorted((root / "simulation_truth").glob("*.json")):
        all_truth.extend(json.loads(path.read_text(encoding="utf-8")))
    # Frozen test months only for event and point metrics. Smoke honestly has N/A test results.
    events = [e for e in all_events if pd.Timestamp(e["start"]).tz_convert(c["timezone"]).month >= 11]
    truth = [t for t in all_truth if pd.Timestamp(t["start"]).month >= 11 and t["observable"]]
    pairs = event_match(events, truth)
    matched_p, matched_t = {p for p, _ in pairs}, {t for _, t in pairs}
    delays, durations = [], []
    for p, t in pairs:
        delays.append(
            (pd.Timestamp(events[p]["start"]) - pd.Timestamp(truth[t]["start"])).total_seconds() / 60
        )
        durations.append(
            abs(
                (pd.Timestamp(events[p]["end"]) - pd.Timestamp(events[p]["start"])).total_seconds()
                - (pd.Timestamp(truth[t]["end"]) - pd.Timestamp(truth[t]["start"])).total_seconds()
            )
            / 60
        )
    point_counts = [0, 0, 0]
    fixed_counts = [0, 0, 0]
    sensitivity = {str(v): [0, 0, 0] for v in [-0.1, -0.2, -0.3]}
    test_days = 0
    for path in sorted((root / "scored").glob("date=*/part.parquet")):
        day = path.parent.name[5:]
        if pd.Timestamp(day).month < 11:
            continue
        s = parquet_read(path)
        test_days += 1
        label = np.zeros(len(s), dtype=bool)
        for t in truth:
            if t["start"][:10] == day:
                label |= (
                    (s.inverter_id == t["inverter_id"])
                    & (s.event_time >= pd.Timestamp(t["start"]))
                    & (s.event_time < pd.Timestamp(t["end"]))
                ).to_numpy()
        gate = ((s.poa_wm2 >= 100) & s.ac_kw.notna() & (s.status != "maintenance")).to_numpy()
        for dest, pred in [
            (point_counts, s.rule_flag.fillna(False).to_numpy(dtype=bool)),
            (fixed_counts, s.fixed_flag.fillna(False).to_numpy(dtype=bool)),
        ]:
            for j, val in enumerate(
                [sum(pred & label & gate), sum(pred & ~label & gate), sum(~pred & label & gate)]
            ):
                dest[j] += int(val)
        for threshold, counts in sensitivity.items():
            pred = (s.physical_deviation < float(threshold)).to_numpy() & gate
            for j, val in enumerate(
                [sum(pred & label & gate), sum(pred & ~label & gate), sum(~pred & label & gate)]
            ):
                counts[j] += int(val)
    fp, fn = (
        [events[i] for i in range(len(events)) if i not in matched_p],
        [truth[i] for i in range(len(truth)) if i not in matched_t],
    )
    ranked = sorted(enumerate(events), key=lambda x: x[1]["evidence"]["physical_deviation_median"])
    k = min(10, len(ranked))
    result = {
        "synthetic": True,
        "run_profile": c["profile"],
        "model_version": VERSION,
        "test_period": "2025-11-01 <= local date < 2026-01-01",
        "model_comparison": comparison,
        "strata": strata,
        "event": classification(len(pairs), len(events) - len(pairs), len(truth) - len(pairs)),
        "point_equipment": classification(*point_counts),
        "fixed_threshold_point": classification(*fixed_counts),
        "quality_evaluation": {
            "status": "quarantine row conservation tested; labeled quality PR not implemented"
        },
        "threshold_sensitivity_point_test_descriptive": {
            t: classification(*v) for t, v in sensitivity.items()
        },
        "threshold_selection": "-0.20 demonstration preset; no claim of validation optimization",
        "precision_at_k": sum(i in matched_p for i, _ in ranked[:k]) / k if k else None,
        "k": k,
        "false_alarms_per_station_day": len(fp) / (c["stations"] * test_days) if test_days else None,
        "mean_delay_minutes": float(np.mean(delays)) if delays else None,
        "mean_duration_error_minutes": float(np.mean(durations)) if durations else None,
        "unobservable_truth_n": sum(not t["observable"] for t in all_truth),
        "fp_examples": fp[:5],
        "fn_examples": fn[:5],
        "event_matching": "chronological prediction, nearest start among overlapping +/-10min, one-to-one",
        "limitation": "Sensor-bias truth treated as equipment candidate; no unique cause attribution. Test sensitivity is descriptive, not tuning.",
    }
    json_write(root / "evaluation.json", result)
    workorders(root)
    return {"input_count": len(test), "output_count": len(events)}

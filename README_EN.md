# Synthetic household PV operations pipeline

**SYNTHETIC DEMO ONLY.** No production records, real household addresses, claimed recovered revenue, or real dispatch.

Bash orchestrates deterministic daily source generation → immutable raw checksums → ODS lineage → DWD quality processing → DWS energy accounting → physical / regression benchmarks → ADS candidate alerts → local workorders → self-contained offline HTML and reports.

Python 3.12 and Bash:

```bash
PV_PYTHON=python3 bash scripts/01_bootstrap.sh
bash scripts/90_demo.sh --config configs/smoke.yaml --run-id smoke
bash scripts/backfill.sh --config configs/demo.yaml --run-id demo-year
# 100 stations, annual theoretical grid: 10,512,000 records
bash scripts/backfill.sh --config configs/full.yaml --run-id full-year
```

Open `runtime/demo/dashboard/dashboard.html`. All JS and aggregated data are embedded. Dates use Asia/Shanghai and an exclusive end. Bounded trapezoidal integration converts kW to kWh; missing observations remain unknown. Communication and observed equipment availability are separate.

The power benchmark uses contemporaneous simulated sensor-style weather, not a day-ahead forecast. HistGradientBoosting fits January–August, selects complexity on September–October, and evaluates November–December. Pre-model dates use an unfitted physical baseline. Truth is consumed only by post-hoc evaluation. Cause outputs are hypotheses requiring human review.

Recovery uses a portable atomic-directory lock, exit-code-aware bounded retries (75 only), dependency/content receipts, atomic output files and a final success watermark. Run `scripts/verify_recovery.py` for executable failure/retry/idempotence/lock checks. CI runs pytest, Ruff, Bash syntax, ShellCheck, SQL and smoke on Ubuntu with read-only repository permissions.

See [Chinese README](README.md), [acceptance and known gaps](docs/acceptance.md), [data contracts](docs/data_dictionary.md), [scenario matrix](docs/scenario_matrix.md), [operations](docs/operations.md), and [sources](docs/sources.md). LSTM is explicitly unimplemented. Docker/PostgreSQL status is reported separately from the tested DuckDB baseline.

"""Verify actual DuckDB SQL, uniqueness and projected partition query plans."""

import argparse
from pathlib import Path

import duckdb

p = argparse.ArgumentParser()
p.add_argument("--root", default="runtime/smoke")
a = p.parse_args()
root = Path(a.root)
with duckdb.connect() as db:
    db.read_parquet((root / "dws/date=*/part.parquet").as_posix()).create_view("dws")
    db.execute(Path("sql/duckdb.sql").read_text(encoding="utf-8"))
    duplicate = db.execute(
        "SELECT count(*) FROM (SELECT inverter_id,event_time,count(*) n "
        "FROM read_parquet(?) GROUP BY 1,2 HAVING count(*)>1)",
        [(root / "dwd/date=*/part.parquet").as_posix()],
    ).fetchone()[0]
    assert duplicate == 0
    plan = db.execute(
        "EXPLAIN ANALYZE SELECT station_id,sum(observed_kwh) "
        "FROM read_parquet(?) WHERE date='2025-01-01' GROUP BY station_id",
        [(root / "dws/date=*/part.parquet").as_posix()],
    ).fetchall()
    print("DWD unique; SQL windows executed; query plan:")
    print(plan[0][1])

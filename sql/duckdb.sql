-- Executed by scripts/verify_sql.py against a completed local runtime.
-- DWD grain (inverter_id,event_time); many-to-one station archive and weather joins.
CREATE OR REPLACE VIEW station_daily AS
SELECT station_id, day, observed_kwh, capacity_kwp, daylight_coverage,
       observed_kwh / NULLIF(capacity_kwp,0) AS specific_yield,
       AVG(observed_kwh / NULLIF(capacity_kwp,0)) OVER
         (PARTITION BY station_id ORDER BY day ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS previous_7_observed
FROM dws;

-- Conditional aggregation keeps status/event dimensions out of numeric averages.
SELECT station_id, COUNT(*) AS station_days,
       SUM(observed_kwh) AS partial_observed_kwh,
       COUNT(*) FILTER (WHERE daylight_coverage >= 0.8) AS sufficient_days
FROM station_daily GROUP BY station_id;

-- Partition pruning/projection can be inspected with EXPLAIN ANALYZE in verify_sql.py.

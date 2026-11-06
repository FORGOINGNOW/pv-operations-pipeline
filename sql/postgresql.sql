-- Optional PostgreSQL 16+ example. Not used by the DuckDB baseline.
BEGIN;
CREATE TABLE IF NOT EXISTS telemetry (
    station_id text NOT NULL,
    inverter_id text NOT NULL,
    event_time timestamptz NOT NULL,
    ingest_time timestamptz NOT NULL,
    ac_kw double precision CHECK (ac_kw >= 0),
    quality_tags text[] NOT NULL DEFAULT '{}',
    source_file text NOT NULL,
    source_line bigint NOT NULL,
    PRIMARY KEY (inverter_id,event_time)
);
CREATE INDEX IF NOT EXISTS telemetry_station_time ON telemetry(station_id,event_time DESC);
CREATE INDEX IF NOT EXISTS telemetry_ingest ON telemetry(ingest_time);
CREATE TABLE IF NOT EXISTS telemetry_stage (LIKE telemetry INCLUDING DEFAULTS);
-- Deduplicate stage first; latest ingest then deterministic source-line precedence.
INSERT INTO telemetry
SELECT DISTINCT ON (inverter_id,event_time) * FROM telemetry_stage
ORDER BY inverter_id,event_time,ingest_time DESC,source_line DESC
ON CONFLICT (inverter_id,event_time) DO UPDATE SET
  ac_kw=excluded.ac_kw, ingest_time=excluded.ingest_time, quality_tags=excluded.quality_tags,
  source_file=excluded.source_file, source_line=excluded.source_line
WHERE (excluded.ingest_time,excluded.source_line) >= (telemetry.ingest_time,telemetry.source_line);
COMMIT;

-- Energy with bounded intervals; input timestamp is absolute, day displayed locally.
WITH intervals AS (
  SELECT *, lag(ac_kw) OVER w AS prev_kw,
    extract(epoch FROM event_time - lag(event_time) OVER w)/3600.0 AS dt_h
  FROM telemetry WINDOW w AS (PARTITION BY inverter_id ORDER BY event_time)
)
SELECT station_id,(event_time AT TIME ZONE 'Asia/Shanghai')::date AS local_day,
  SUM(CASE WHEN dt_h > 0 AND dt_h <= 10.0/60 THEN (prev_kw+ac_kw)/2*dt_h END) AS observed_kwh
FROM intervals GROUP BY 1,2;
-- Production adaptation must clip intervals crossing midnight, as core.integrate does.

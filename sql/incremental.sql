-- Deterministic staging deduplication followed by incremental upsert.
INSERT INTO dwd_telemetry
SELECT station_id,inverter_id,event_time,ingest_time,sequence_no,source_line,ac_kw,quality_tags
FROM telemetry_stage
QUALIFY row_number() OVER (
    PARTITION BY inverter_id,event_time
    ORDER BY ingest_time DESC,sequence_no DESC,source_line DESC
) = 1
ON CONFLICT(inverter_id,event_time) DO UPDATE SET
    ingest_time=excluded.ingest_time,sequence_no=excluded.sequence_no,
    source_line=excluded.source_line,ac_kw=excluded.ac_kw,quality_tags=excluded.quality_tags
WHERE (excluded.ingest_time,excluded.sequence_no,excluded.source_line)
   >= (dwd_telemetry.ingest_time,dwd_telemetry.sequence_no,dwd_telemetry.source_line);

-- Minimal relational contracts mirroring the Parquet baseline. Executed in verify_sql.py.
CREATE TABLE ods_raw (
    source_file VARCHAR NOT NULL, source_line BIGINT NOT NULL, source_byte BIGINT NOT NULL,
    payload VARCHAR NOT NULL, PRIMARY KEY(source_file, source_line)
);
CREATE TABLE dwd_telemetry (
    station_id VARCHAR NOT NULL, inverter_id VARCHAR NOT NULL,
    event_time TIMESTAMPTZ NOT NULL, ingest_time TIMESTAMPTZ NOT NULL,
    sequence_no BIGINT NOT NULL, source_line BIGINT NOT NULL,
    ac_kw DOUBLE CHECK(ac_kw >= 0), quality_tags VARCHAR NOT NULL,
    PRIMARY KEY(inverter_id, event_time)
);
CREATE TABLE dws_station_day (
    station_id VARCHAR NOT NULL, day DATE NOT NULL,
    observed_kwh DOUBLE, estimated_kwh DOUBLE,
    capacity_kwp DOUBLE CHECK(capacity_kwp > 0),
    daylight_coverage DOUBLE CHECK(daylight_coverage BETWEEN 0 AND 1),
    confidence VARCHAR NOT NULL, PRIMARY KEY(station_id, day)
);
CREATE TABLE ads_station_risk (
    station_id VARCHAR NOT NULL, day DATE NOT NULL, rule_version VARCHAR NOT NULL,
    suspected_loss_kwh DOUBLE, uncertainty VARCHAR NOT NULL,
    PRIMARY KEY(station_id, day, rule_version)
);

# Deterministic boundary fixtures

`test_business.py:message()` constructs exact fixtures without random draws. T01–T14
cover irregular integration, day clipping, counter reset/rollover, unit/time parsing,
quarantine, lateness, deterministic generation, peers, elapsed duration, label isolation,
matching, clipping/night, multi-inverter cardinality and archive expiry.

The source generator uses deterministic per-station/day seeds; no real household records.

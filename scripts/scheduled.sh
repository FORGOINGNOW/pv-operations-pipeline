#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export TZ=Asia/Shanghai
DAY="$(date -d yesterday +%F)"
# This template is Linux-only. Historical demo data normally uses explicit backfill.
exec bash scripts/run_daily.sh --config configs/full.yaml --date "$DAY"

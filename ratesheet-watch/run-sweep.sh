#!/usr/bin/env bash
# Daily ratesheet-watch sweep (cron entry point). Logs to reports/cron.log.
set -uo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
mkdir -p reports
{
  echo "=== sweep $(date '+%Y-%m-%d %H:%M:%S') ==="
  .venv/bin/python sweep.py --pilot
} >> reports/cron.log 2>&1

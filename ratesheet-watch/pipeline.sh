#!/usr/bin/env bash
# Phase-2 pipeline: hand each new change report to /ratesheet-change.
# DRY-RUN by default; pass --live to actually invoke claude.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
LIVE=false
DATE=$(date +%Y%m%d)
for arg in "$@"; do
  case "$arg" in
    --live) LIVE=true ;;
    --date=*) DATE="${arg#--date=}" ;;
  esac
done

REPORTS="$DIR/reports/$DATE"
[ -d "$REPORTS" ] || { echo "no reports for $DATE"; exit 0; }

for report in "$REPORTS"/*.md; do
  [ -e "$report" ] || continue
  base=$(basename "$report")
  [ "$base" = "digest.md" ] && continue
  if $LIVE; then
    echo "→ handling $report"
    claude -p "/ratesheet-change $report" --permission-mode acceptEdits \
      --max-turns 200 || echo "PIPELINE_FAILED: $report"
  else
    echo "[dry-run] would handle: $report"
  fi
done

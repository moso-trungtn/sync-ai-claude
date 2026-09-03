#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/openjdk@21/bin:/Users/trungthach/.local/bin:/Users/trungthach/google-cloud-sdk/bin:/usr/bin:/bin"
[ -f ~/.config/parser-bot/env ] && set -a && . ~/.config/parser-bot/env && set +a   # JIRA_EMAIL, JIRA_API_TOKEN
exec .venv/bin/python -m parser_bot.bot "$@"

#!/usr/bin/env bash
# Hook: PostToolUse for Agent tool
# Triggered AFTER any agent completes.
# Reads tool result from stdin.

EVENTS_DIR="/tmp/agent-dashboard"
EVENTS_FILE="$EVENTS_DIR/events.jsonl"

mkdir -p "$EVENTS_DIR"

INPUT=$(cat)

# Extract result info
PARSED=$(echo "$INPUT" | python3 -c "
import sys,json
d=json.load(sys.stdin)
ti = d.get('tool_input',{})
r = d.get('tool_result','')
result_str = str(r)
has_error = 'true' if 'error' in result_str.lower()[:200] else 'false'
print(ti.get('description','unknown'))
print(ti.get('subagent_type','general-purpose'))
print(has_error)
print(len(result_str))
" 2>/dev/null || echo "unknown
general-purpose
false
0")

DESCRIPTION=$(echo "$PARSED" | sed -n '1p')
AGENT_TYPE=$(echo "$PARSED" | sed -n '2p')
HAS_ERROR=$(echo "$PARSED" | sed -n '3p')
RESULT_CHARS=$(echo "$PARSED" | sed -n '4p')

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

_esc() { python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()), end='')" <<< "$1"; }

DESC_ESC=$(_esc "$DESCRIPTION")
TYPE_ESC=$(_esc "$AGENT_TYPE")

if [ "$HAS_ERROR" = "true" ]; then
  STATUS="failed"
  LEVEL="error"
else
  STATUS="completed"
  LEVEL="success"
fi

echo "{\"type\":\"agent:done\",\"agentType\":$TYPE_ESC,\"description\":$DESC_ESC,\"status\":\"$STATUS\",\"resultChars\":$RESULT_CHARS,\"time\":\"$TIMESTAMP\",\"message\":\"$AGENT_TYPE $STATUS: $DESCRIPTION\",\"level\":\"$LEVEL\"}" >> "$EVENTS_FILE"

#!/usr/bin/env bash
# Hook: PreToolUse for Agent tool
# Triggered BEFORE any agent is spawned.
# Reads tool input from stdin (JSON with tool_input.prompt, tool_input.description, etc.)
# Emits agent:start event and auto-launches dashboard if not running.

DASHBOARD_DIR="$(cd "$(dirname "$0")" && pwd)"
EVENTS_DIR="/tmp/agent-dashboard"
EVENTS_FILE="$EVENTS_DIR/events.jsonl"
PID_FILE="$EVENTS_DIR/server.pid"
PORT=3847

mkdir -p "$EVENTS_DIR"

# Read hook input from stdin
INPUT=$(cat)

# Extract agent info from JSON
PARSED=$(echo "$INPUT" | python3 -c "
import sys,json
d=json.load(sys.stdin)
ti = d.get('tool_input',{})
prompt = ti.get('prompt','')
# Detect origin: 'auto' for built-in subagent types, 'custom' for user-defined
stype = ti.get('subagent_type','general-purpose')
auto_types = ['Explore', 'Plan', 'claude-code-guide', 'statusline-setup']
origin = 'auto' if stype in auto_types else 'custom'
# If general-purpose, check for model override or specific patterns
if stype == 'general-purpose' and not ti.get('model'):
    origin = 'auto'
print(ti.get('description','unknown'))
print(stype)
print(ti.get('run_in_background','false'))
print(len(prompt))
print(origin)
" 2>/dev/null || echo "unknown
general-purpose
false
0
auto")

DESCRIPTION=$(echo "$PARSED" | sed -n '1p')
AGENT_TYPE=$(echo "$PARSED" | sed -n '2p')
BACKGROUND=$(echo "$PARSED" | sed -n '3p')
PROMPT_CHARS=$(echo "$PARSED" | sed -n '4p')
ORIGIN=$(echo "$PARSED" | sed -n '5p')

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
AGENT_ID="agent-$(date +%s%N | cut -c1-13)"

# JSON-escape strings
_esc() { python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()), end='')" <<< "$1"; }

DESC_ESC=$(_esc "$DESCRIPTION")
TYPE_ESC=$(_esc "$AGENT_TYPE")

# Emit agent start event
echo "{\"type\":\"agent:spawn\",\"agentId\":\"$AGENT_ID\",\"agentType\":$TYPE_ESC,\"description\":$DESC_ESC,\"background\":$BACKGROUND,\"promptChars\":$PROMPT_CHARS,\"origin\":\"$ORIGIN\",\"time\":\"$TIMESTAMP\",\"message\":\"Spawning $AGENT_TYPE: $DESCRIPTION\"}" >> "$EVENTS_FILE"

# Auto-launch dashboard server if not running
if [ -f "$PID_FILE" ]; then
  EXISTING_PID=$(cat "$PID_FILE")
  if ! kill -0 "$EXISTING_PID" 2>/dev/null; then
    rm -f "$PID_FILE"
  fi
fi

if [ ! -f "$PID_FILE" ]; then
  # Start server in background
  nohup python3 "$DASHBOARD_DIR/server.py" > "$EVENTS_DIR/server.log" 2>&1 &
  echo $! > "$PID_FILE"
  sleep 0.5

  # Auto-open browser
  if command -v open &>/dev/null; then
    open "http://localhost:$PORT" 2>/dev/null &
  fi
fi

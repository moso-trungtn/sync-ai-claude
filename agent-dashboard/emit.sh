#!/usr/bin/env bash
# Agent Team Event Emitter
#
# Usage:
#   source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
#
# Then use these functions:
#   emit_pipeline_start "ba-lead"
#   emit_pipeline_phase "dev-lead"
#   emit_pipeline_retry 1
#   emit_pipeline_done
#   emit_meta "MOSO-14658" "PennyMac" "Add USDA program"
#   emit_agent_start "ba-lead" "Fetching Jira task"
#   emit_agent_step "ba-lead" "Analyzing screenshots"
#   emit_agent_subtask "ba-lead" "Fetch Jira" "completed" "Downloaded 4 images"
#   emit_agent_file "dev-lead" "PennyMacTables.java" "modified"
#   emit_agent_test "qc-lead" "Build" "PASS" "BUILD SUCCESS"
#   emit_agent_output "ba-lead" "Some text output"
#   emit_agent_complete "ba-lead"
#   emit_agent_fail "ba-lead" "Error message"
#   emit_log "ba-lead" "info" "Some log message"

EVENTS_DIR="/tmp/agent-dashboard"
EVENTS_FILE="$EVENTS_DIR/events.jsonl"

_ensure_dir() {
    mkdir -p "$EVENTS_DIR"
}

_timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

_emit() {
    _ensure_dir
    echo "$1" >> "$EVENTS_FILE"
}

_json_escape() {
    echo -n "$1" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()), end='')"
}

# Pipeline ID — set this before emitting pipeline events to group them.
# Defaults to a timestamp-based ID if not set.
# Usage: PIPELINE_ID="parser-PennyMac-USDA" or let it auto-generate.
PIPELINE_ID="${PIPELINE_ID:-}"

_pipeline_id() {
    if [ -z "$PIPELINE_ID" ]; then
        PIPELINE_ID="pipeline-$(date +%s)"
    fi
    echo "$PIPELINE_ID"
}

emit_pipeline_start() {
    local phase="${1:-ba-lead}"
    local name="${2:-}"
    local pid=$(_pipeline_id)
    _emit "{\"type\":\"pipeline:start\",\"pipelineId\":\"$pid\",\"pipelineName\":\"$name\",\"phase\":\"$phase\",\"time\":\"$(_timestamp)\",\"message\":\"Pipeline started: $name\"}"
}

emit_pipeline_phase() {
    local phase="$1"
    local pid=$(_pipeline_id)
    _emit "{\"type\":\"pipeline:phase\",\"pipelineId\":\"$pid\",\"phase\":\"$phase\",\"time\":\"$(_timestamp)\",\"message\":\"Phase: $phase\"}"
}

emit_pipeline_retry() {
    local count="$1"
    local pid=$(_pipeline_id)
    _emit "{\"type\":\"pipeline:retry\",\"pipelineId\":\"$pid\",\"count\":$count,\"time\":\"$(_timestamp)\",\"message\":\"Retry #$count\"}"
}

emit_pipeline_done() {
    local pid=$(_pipeline_id)
    _emit "{\"type\":\"pipeline:done\",\"pipelineId\":\"$pid\",\"time\":\"$(_timestamp)\",\"message\":\"Pipeline completed\",\"level\":\"success\"}"
    PIPELINE_ID=""
}

emit_meta() {
    local jira="$1" lender="$2" action="$3"
    local pid=$(_pipeline_id)
    _emit "{\"type\":\"meta\",\"pipelineId\":\"$pid\",\"jiraKey\":\"$jira\",\"lender\":\"$lender\",\"action\":\"$action\",\"time\":\"$(_timestamp)\"}"
}

emit_agent_start() {
    local agent="$1" step="$2"
    local msg=$(_json_escape "$step")
    _emit "{\"type\":\"agent:start\",\"agent\":\"$agent\",\"step\":$msg,\"time\":\"$(_timestamp)\",\"message\":\"$agent started: $step\"}"
}

emit_agent_step() {
    local agent="$1" step="$2"
    local msg=$(_json_escape "$step")
    _emit "{\"type\":\"agent:step\",\"agent\":\"$agent\",\"step\":$msg,\"time\":\"$(_timestamp)\",\"message\":$msg}"
}

emit_agent_subtask() {
    local agent="$1" name="$2" status="$3" detail="${4:-}"
    local n=$(_json_escape "$name")
    local d=$(_json_escape "$detail")
    _emit "{\"type\":\"agent:subtask\",\"agent\":\"$agent\",\"name\":$n,\"status\":\"$status\",\"detail\":$d,\"time\":\"$(_timestamp)\",\"message\":\"[$status] $name\"}"
}

emit_agent_file() {
    local agent="$1" path="$2" change="${3:-modified}"
    local p=$(_json_escape "$path")
    _emit "{\"type\":\"agent:file\",\"agent\":\"$agent\",\"path\":$p,\"change\":\"$change\",\"time\":\"$(_timestamp)\",\"message\":\"$change: $path\"}"
}

emit_agent_test() {
    local agent="$1" name="$2" status="$3" detail="${4:-}"
    local n=$(_json_escape "$name")
    local d=$(_json_escape "$detail")
    local level="info"
    [ "$status" = "FAIL" ] && level="error"
    [ "$status" = "PASS" ] && level="success"
    _emit "{\"type\":\"agent:test\",\"agent\":\"$agent\",\"name\":$n,\"status\":\"$status\",\"detail\":$d,\"time\":\"$(_timestamp)\",\"message\":\"$name: $status\",\"level\":\"$level\"}"
}

emit_agent_output() {
    local agent="$1" text="$2"
    local t=$(_json_escape "$text")
    _emit "{\"type\":\"agent:output\",\"agent\":\"$agent\",\"text\":$t,\"time\":\"$(_timestamp)\"}"
}

emit_agent_complete() {
    local agent="$1" status="${2:-completed}"
    _emit "{\"type\":\"agent:complete\",\"agent\":\"$agent\",\"status\":\"$status\",\"time\":\"$(_timestamp)\",\"message\":\"$agent $status\",\"level\":\"success\"}"
}

emit_agent_fail() {
    local agent="$1" error="$2"
    local e=$(_json_escape "$error")
    _emit "{\"type\":\"agent:fail\",\"agent\":\"$agent\",\"error\":$e,\"time\":\"$(_timestamp)\",\"message\":\"$agent failed: $error\",\"level\":\"error\"}"
}

emit_log() {
    local agent="$1" level="$2" message="$3"
    local m=$(_json_escape "$message")
    _emit "{\"type\":\"log\",\"agent\":\"$agent\",\"level\":\"$level\",\"message\":$m,\"time\":\"$(_timestamp)\"}"
}

emit_reset() {
    _ensure_dir
    > "$EVENTS_FILE"
}

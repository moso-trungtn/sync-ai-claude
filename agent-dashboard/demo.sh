#!/usr/bin/env bash
# Demo script to test the dashboard with simulated events
# Run this while the dashboard server is running to see it in action.
#
# Usage:
#   Terminal 1: python3 server.py
#   Terminal 2: bash demo.sh

source "$(dirname "$0")/emit.sh"

# Also inject some universal agent events to demo the All Agents tab
EVENTS_DIR="/tmp/agent-dashboard"
mkdir -p "$EVENTS_DIR"

echo "Starting demo... Open http://localhost:3847"
echo ""

emit_reset
sleep 0.5

# Simulate universal agent spawns (as if hooks captured them)
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "{\"type\":\"agent:spawn\",\"agentId\":\"agent-1001\",\"agentType\":\"Explore\",\"description\":\"Explore PennyMac parser structure\",\"background\":false,\"time\":\"$TS\",\"message\":\"Spawning Explore: Explore PennyMac parser structure\"}" >> "$EVENTS_DIR/events.jsonl"
sleep 0.3
echo "{\"type\":\"agent:done\",\"agentType\":\"Explore\",\"description\":\"Explore PennyMac parser structure\",\"status\":\"completed\",\"time\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"message\":\"Explore completed: Explore PennyMac parser structure\",\"level\":\"success\"}" >> "$EVENTS_DIR/events.jsonl"
sleep 0.3
echo "{\"type\":\"agent:spawn\",\"agentId\":\"agent-1002\",\"agentType\":\"general-purpose\",\"description\":\"BA Lead: analyze parser task\",\"background\":false,\"time\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"message\":\"Spawning general-purpose: BA Lead: analyze parser task\"}" >> "$EVENTS_DIR/events.jsonl"
sleep 0.5

# Pipeline start
emit_pipeline_start "ba-lead"
emit_meta "MOSO-14658" "PennyMac" "Add USDA program"
sleep 1

# BA Lead
emit_agent_start "ba-lead" "Fetching Jira task"
sleep 1.5
emit_agent_step "ba-lead" "Downloading attachments"
sleep 1
emit_agent_step "ba-lead" "Analyzing screenshots"
sleep 1.5
emit_agent_step "ba-lead" "Reading existing PennyMac code"
sleep 1
emit_agent_subtask "ba-lead" "Update PennyMacTables.java" "pending" "Add USDA FICO/LTV, misc adj, validators"
emit_agent_subtask "ba-lead" "Update PennyMacXLSXParser.java" "pending" "Add USDA rate sheet processing"
emit_agent_subtask "ba-lead" "Update PennyMacAdjustmentXlsxParser.java" "pending" "Add USDA section extraction"
emit_agent_subtask "ba-lead" "Update lender documentation" "pending" "Add USDA section to pennymac.md"
sleep 0.5
emit_agent_complete "ba-lead"
sleep 1

# User confirm
emit_pipeline_phase "user-confirm"
emit_log "system" "info" "Waiting for user to confirm plan and provide ratesheet path..."
sleep 3

# Dev Lead
emit_pipeline_phase "dev-lead"
emit_agent_start "dev-lead" "Planning implementation"
sleep 1

emit_agent_step "dev-lead" "Reading PennyMacTables.java"
sleep 1
emit_agent_subtask "dev-lead" "Update PennyMacTables.java" "running" "Adding USDA tables"
sleep 2
emit_agent_file "dev-lead" "moso-pricing/.../PennyMacTables.java" "modified"
emit_agent_subtask "dev-lead" "Update PennyMacTables.java" "completed" "Added 3 tables + 4 validators"
sleep 0.5

emit_agent_subtask "dev-lead" "Update PennyMacXLSXParser.java" "running" "Adding USDA rate products"
sleep 1.5
emit_agent_file "dev-lead" "moso-pricing/.../PennyMacXLSXParser.java" "modified"
emit_agent_subtask "dev-lead" "Update PennyMacXLSXParser.java" "completed" "Added 8 rate products"
sleep 0.5

emit_agent_subtask "dev-lead" "Update PennyMacAdjustmentXlsxParser.java" "running" "Adding USDA section parsing"
sleep 1.5
emit_agent_file "dev-lead" "moso-pricing/.../PennyMacAdjustmentXlsxParser.java" "modified"
emit_agent_subtask "dev-lead" "Update PennyMacAdjustmentXlsxParser.java" "completed" "Added USDA section"
sleep 0.5

emit_agent_step "dev-lead" "Building moso-pricing"
sleep 2
emit_agent_subtask "dev-lead" "Update lender documentation" "completed" "Updated pennymac.md"
emit_agent_file "dev-lead" "moso-pricing/docs/lenders/pennymac.md" "modified"
emit_agent_complete "dev-lead"
sleep 1

# QC Lead
emit_pipeline_phase "qc-lead"
emit_agent_start "qc-lead" "Running tests"
sleep 1

emit_agent_step "qc-lead" "Verifying build"
emit_agent_test "qc-lead" "Build" "PASS" "BUILD SUCCESS in 12s"
sleep 1

emit_agent_step "qc-lead" "Running adjustment parser test"
emit_agent_test "qc-lead" "Adj Parser Test" "PASS" "All expectations match"
sleep 1.5

emit_agent_step "qc-lead" "Running rate parser test"
emit_agent_test "qc-lead" "Rate Parser Test" "PASS" "150 products, 2890 rates"
sleep 1

emit_agent_step "qc-lead" "Validating code quality"
emit_agent_test "qc-lead" "Field Uniqueness" "PASS" "No duplicate fields"
emit_agent_test "qc-lead" "allTables Complete" "PASS" "58 tables listed"
emit_agent_test "qc-lead" "calculators Complete" "PASS" "All tables have calculators"
emit_agent_test "qc-lead" "Mode Alignment" "PASS" "All modes resolve"
emit_agent_test "qc-lead" "Range Directions" "PASS" "FICO desc, LTV asc"
emit_agent_test "qc-lead" "crawlLabels Count" "PASS" "Labels match ranges"
sleep 1

emit_agent_complete "qc-lead"
sleep 0.5

# Done!
emit_pipeline_phase "finalize"
sleep 1
emit_pipeline_done

echo ""
echo "Demo complete! Check the dashboard."

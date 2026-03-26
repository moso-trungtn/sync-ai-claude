#!/usr/bin/env python3
"""
Universal Agent Dashboard Server

Serves the dashboard HTML and aggregates agent events from:
1. Hook events (auto-captured from ALL agent spawns via Claude Code hooks)
2. Manual emit events (from /new-parser skill or other skills)

Events file: /tmp/agent-dashboard/events.jsonl

API Endpoints:
    GET /              → serves dashboard.html
    GET /status        → aggregated agent state from events.jsonl (includes tokenUsage)
    GET /reset         → clears events
    GET /api/skills    → list all skills from ~/.claude/skills/
    GET /api/plugins   → list plugins from ~/.claude/plugins/installed_plugins.json
    GET /api/settings  → current settings from ~/.claude/settings.json
    GET /api/memory    → list memory files
    DELETE /api/memory?file=<name> → delete a memory file and update MEMORY.md index
    GET /api/token-usage     → real token usage per agent from subagent transcripts
    GET /api/file?path=<path> → read a file (only under ~/.claude/)

Usage:
    python3 server.py [--port 3847]
    # Then open http://localhost:3847
"""

import glob
import http.server
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PORT = 3847
STATUS_DIR = Path("/tmp/agent-dashboard")
EVENTS_FILE = STATUS_DIR / "events.jsonl"
DASHBOARD_FILE = Path(__file__).parent / "dashboard.html"
CLAUDE_DIR = Path.home() / ".claude"
MEMORY_DIR = CLAUDE_DIR / "projects" / "-Users-trungthach-IdeaProjects" / "memory"
PROJECTS_DIR = CLAUDE_DIR / "projects"
PLAN_CONFIG_FILE = STATUS_DIR / "plan-config.json"

# Default plan config (user can update via API)
DEFAULT_PLAN = {
    "name": "Max $100",
    "monthlyTokenLimit": 0,  # 0 = unknown/unlimited, user can set this
    "billingCycleStart": "",  # ISO date, e.g. "2026-03-01"
}

# Patterns that indicate secrets in settings
SECRET_PATTERNS = re.compile(
    r"(token|password|secret|key|api_key|apikey|auth|credential|private)",
    re.IGNORECASE,
)

# Cache for token usage (expensive to compute — scans all transcript files)
_token_usage_cache = {"data": None, "timestamp": 0}
TOKEN_CACHE_TTL = 60  # seconds


def build_state_from_events():
    """Read events.jsonl and build current state."""
    state = {
        "agents": [],
        "activeCount": 0,
        "completedCount": 0,
        "failedCount": 0,
        "totalCount": 0,
        "pipeline": None,
        "pipelines": [],
        "meta": {},
        "log": [],
    }

    if not EVENTS_FILE.exists():
        return state

    agents_by_desc = {}
    pipeline_state = None
    pipelines_by_id = {}

    def _make_pipeline(pid, name, ts, phase="ba-lead"):
        return {
            "pipelineId": pid,
            "pipelineName": name,
            "phase": phase,
            "startedAt": ts,
            "retryCount": 0,
            "meta": {},
            "agents": {
                "ba-lead": {"status": "pending", "step": "", "subtasks": [], "startedAt": None, "completedAt": None, "tests": [], "files": [], "output": ""},
                "dev-lead": {"status": "pending", "step": "", "subtasks": [], "startedAt": None, "completedAt": None, "tests": [], "files": [], "output": ""},
                "qc-lead": {"status": "pending", "step": "", "subtasks": [], "startedAt": None, "completedAt": None, "tests": [], "files": [], "output": ""},
            },
        }

    try:
        with open(EVENTS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                etype = event.get("type", "")
                ts = event.get("time", "")

                # Universal agent tracking (from hooks)
                if etype == "agent:spawn":
                    desc = event.get("description", "unknown")
                    prompt_chars = event.get("promptChars", 0)
                    agent_entry = {
                        "id": event.get("agentId", f"agent-{len(agents_by_desc)}"),
                        "type": event.get("agentType", "general-purpose"),
                        "description": desc,
                        "status": "running",
                        "background": event.get("background", False),
                        "startedAt": ts,
                        "completedAt": None,
                        "promptChars": prompt_chars,
                        "resultChars": 0,
                        "estimatedInputTokens": max(1, prompt_chars // 4),
                        "estimatedOutputTokens": 0,
                        "steps": [],
                        "files": [],
                        "tests": [],
                        "subtasks": [],
                    }
                    agents_by_desc[desc] = agent_entry
                    state["agents"].append(agent_entry)

                elif etype == "agent:done":
                    desc = event.get("description", "")
                    status = event.get("status", "completed")
                    result_chars = event.get("resultChars", 0)
                    if desc in agents_by_desc:
                        agents_by_desc[desc]["status"] = status
                        agents_by_desc[desc]["completedAt"] = ts
                        agents_by_desc[desc]["resultChars"] = result_chars
                        agents_by_desc[desc]["estimatedOutputTokens"] = max(1, result_chars // 4)

                # Pipeline events (supports multiple pipelines via pipelineId)
                elif etype == "pipeline:start":
                    pid = event.get("pipelineId", f"pipeline-{len(pipelines_by_id)}")
                    name = event.get("pipelineName", "")
                    ps = _make_pipeline(pid, name, ts, event.get("phase", "ba-lead"))
                    pipelines_by_id[pid] = ps
                    pipeline_state = ps  # current/latest pipeline

                elif etype == "pipeline:phase":
                    pid = event.get("pipelineId", "")
                    target = pipelines_by_id.get(pid, pipeline_state)
                    if target:
                        target["phase"] = event.get("phase", "")

                elif etype == "pipeline:retry":
                    pid = event.get("pipelineId", "")
                    target = pipelines_by_id.get(pid, pipeline_state)
                    if target:
                        target["retryCount"] = event.get("count", 0)

                elif etype == "pipeline:done":
                    pid = event.get("pipelineId", "")
                    target = pipelines_by_id.get(pid, pipeline_state)
                    if target:
                        target["phase"] = "done"

                elif etype == "meta":
                    pid = event.get("pipelineId", "")
                    meta_data = {k: v for k, v in event.items() if k in ("jiraKey", "lender", "action")}
                    state["meta"].update(meta_data)
                    # Also attach meta to specific pipeline
                    target = pipelines_by_id.get(pid, pipeline_state)
                    if target:
                        target["meta"].update(meta_data)

                # Pipeline agent-specific events
                elif etype.startswith("agent:") and pipeline_state:
                    agent = event.get("agent", "")
                    pid = event.get("pipelineId", "")
                    target_pipeline = pipelines_by_id.get(pid, pipeline_state)
                    if target_pipeline and agent in target_pipeline.get("agents", {}):
                        pa = target_pipeline["agents"][agent]

                        if etype == "agent:start":
                            pa["status"] = "running"
                            pa["startedAt"] = ts
                            pa["step"] = event.get("step", "Starting...")

                        elif etype == "agent:step":
                            pa["step"] = event.get("step", "")

                        elif etype == "agent:subtask":
                            name = event.get("name", "")
                            found = False
                            for st in pa["subtasks"]:
                                if st["name"] == name:
                                    st["status"] = event.get("status", "pending")
                                    if event.get("detail"):
                                        st["detail"] = event["detail"]
                                    found = True
                                    break
                            if not found:
                                pa["subtasks"].append({
                                    "name": name,
                                    "status": event.get("status", "pending"),
                                    "detail": event.get("detail", ""),
                                })

                        elif etype == "agent:file":
                            pa["files"].append({
                                "path": event.get("path", ""),
                                "type": event.get("change", "modified"),
                            })

                        elif etype == "agent:test":
                            pa["tests"].append({
                                "name": event.get("name", ""),
                                "status": event.get("status", ""),
                                "detail": event.get("detail", ""),
                            })

                        elif etype == "agent:output":
                            pa["output"] += event.get("text", "") + "\n"

                        elif etype == "agent:complete":
                            pa["status"] = event.get("status", "completed")
                            pa["completedAt"] = ts

                        elif etype == "agent:fail":
                            pa["status"] = "failed"
                            pa["completedAt"] = ts
                            pa["step"] = event.get("error", "Failed")

                # Log entry
                if event.get("message"):
                    state["log"].append({
                        "time": ts,
                        "agent": event.get("agent", event.get("agentType", "system")),
                        "message": event["message"],
                        "level": event.get("level", "info"),
                    })

        state["pipeline"] = pipeline_state  # latest pipeline (backwards compat)
        state["pipelines"] = list(pipelines_by_id.values())

        # Count agents and token usage
        total_input_tokens = 0
        total_output_tokens = 0
        for a in state["agents"]:
            if a["status"] == "running":
                state["activeCount"] += 1
            elif a["status"] == "completed":
                state["completedCount"] += 1
            elif a["status"] == "failed":
                state["failedCount"] += 1
            total_input_tokens += a.get("estimatedInputTokens", 0)
            total_output_tokens += a.get("estimatedOutputTokens", 0)
        state["totalCount"] = len(state["agents"])

    except Exception as e:
        state["log"].append({
            "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "agent": "system",
            "message": f"Error reading events: {e}",
            "level": "error",
        })

    return state


def get_custom_agents():
    """Scan for custom agent definitions from ~/.claude/agents/ and plugins."""
    agents = []

    # User-defined agents
    user_agents_dir = CLAUDE_DIR / "agents"
    if user_agents_dir.exists():
        for f in sorted(user_agents_dir.glob("*.md")):
            agents.append(_parse_agent_file(f, "user"))

    # Plugin agents
    plugins_dir = CLAUDE_DIR / "plugins" / "marketplaces"
    if plugins_dir.exists():
        for agent_file in sorted(plugins_dir.rglob("agents/*.md")):
            agents.append(_parse_agent_file(agent_file, "plugin"))

    return agents


def _parse_agent_file(filepath, source):
    """Parse an agent .md file with YAML frontmatter."""
    name = filepath.stem
    description = ""
    model = ""
    color = ""
    tools = ""
    try:
        content = filepath.read_text(encoding="utf-8")
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().split("\n"):
                    line = line.strip()
                    if line.startswith("name:"):
                        name = line[5:].strip().strip("\"'")
                    elif line.startswith("description:"):
                        description = line[12:].strip().strip("\"'")
                    elif line.startswith("model:"):
                        model = line[6:].strip().strip("\"'")
                    elif line.startswith("color:"):
                        color = line[6:].strip().strip("\"'")
                    elif line.startswith("tools:"):
                        tools = line[6:].strip()
    except Exception:
        pass
    return {
        "name": name,
        "description": description,
        "model": model,
        "color": color,
        "tools": tools,
        "source": source,
        "path": str(filepath),
    }


def get_skills():
    """Scan ~/.claude/skills/*/SKILL.md and parse YAML frontmatter."""
    skills_dir = CLAUDE_DIR / "skills"
    skills = []
    if not skills_dir.exists():
        return skills

    for skill_dir in sorted(skills_dir.iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        name = skill_dir.name
        description = ""
        path = str(skill_file)

        try:
            content = skill_file.read_text(encoding="utf-8")
            # Parse YAML frontmatter between --- markers
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = parts[1]
                    for line in frontmatter.strip().split("\n"):
                        line = line.strip()
                        if line.startswith("name:"):
                            name = line[5:].strip().strip('"').strip("'")
                        elif line.startswith("description:"):
                            description = line[12:].strip().strip('"').strip("'")
        except Exception:
            pass

        skills.append({"name": name, "description": description, "path": path})

    return skills


def get_plugins():
    """Read installed plugins and discover marketplace plugins with their skills/agents."""
    result = {"installed": [], "marketplace": []}

    # Installed plugins (from installed_plugins.json)
    plugins_file = CLAUDE_DIR / "plugins" / "installed_plugins.json"
    if plugins_file.exists():
        try:
            data = json.loads(plugins_file.read_text(encoding="utf-8"))
            plugins_dict = data.get("plugins", data) if isinstance(data, dict) else {}
            if isinstance(plugins_dict, dict) and "plugins" in plugins_dict:
                plugins_dict = plugins_dict["plugins"]
            if isinstance(plugins_dict, dict):
                for name, entries in plugins_dict.items():
                    entry = entries[0] if isinstance(entries, list) and entries else {}
                    result["installed"].append({
                        "name": name,
                        "scope": entry.get("scope", ""),
                        "version": entry.get("version", ""),
                        "installedAt": entry.get("installedAt", ""),
                    })
        except Exception:
            pass

    # Marketplace plugins (from marketplaces directory)
    marketplace_dir = CLAUDE_DIR / "plugins" / "marketplaces"
    if marketplace_dir.exists():
        for market in marketplace_dir.iterdir():
            if not market.is_dir():
                continue
            plugins_dir = market / "plugins"
            if not plugins_dir.exists():
                continue
            for plugin_dir in sorted(plugins_dir.iterdir()):
                if not plugin_dir.is_dir():
                    continue
                plugin_name = plugin_dir.name
                description = ""
                skills = []
                agents = []

                # Check for plugin.json or README
                plugin_json = plugin_dir / "plugin.json"
                if plugin_json.exists():
                    try:
                        pdata = json.loads(plugin_json.read_text(encoding="utf-8"))
                        description = pdata.get("description", "")
                    except Exception:
                        pass

                # Find skills
                skills_dir = plugin_dir / "skills"
                if skills_dir.exists():
                    for sd in skills_dir.iterdir():
                        if sd.is_dir():
                            skill_file = sd / "SKILL.md"
                            sname = sd.name
                            if skill_file.exists():
                                try:
                                    content = skill_file.read_text(encoding="utf-8")
                                    if content.startswith("---"):
                                        parts = content.split("---", 2)
                                        if len(parts) >= 3:
                                            for line in parts[1].strip().split("\n"):
                                                if line.strip().startswith("name:"):
                                                    sname = line.split(":", 1)[1].strip().strip("\"'")
                                                    break
                                except Exception:
                                    pass
                            skills.append(sname)

                # Find agents
                agents_dir = plugin_dir / "agents"
                if agents_dir.exists():
                    for af in agents_dir.glob("*.md"):
                        agents.append(af.stem)

                # Check if installed
                is_installed = any(
                    plugin_name in inst.get("name", "")
                    for inst in result["installed"]
                )

                result["marketplace"].append({
                    "name": plugin_name,
                    "description": description,
                    "marketplace": market.name,
                    "skills": skills,
                    "agents": agents,
                    "installed": is_installed,
                })

    return result


def get_settings():
    """Read ~/.claude/settings.json with secret redaction."""
    settings_file = CLAUDE_DIR / "settings.json"
    if not settings_file.exists():
        return {}
    try:
        settings = json.loads(settings_file.read_text(encoding="utf-8"))
        return redact_secrets(settings)
    except Exception:
        return {}


def redact_secrets(obj, parent_key=""):
    """Recursively redact values that look like secrets."""
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if SECRET_PATTERNS.search(k) and isinstance(v, str):
                result[k] = "***REDACTED***"
            elif k == "env" and isinstance(v, dict):
                # Redact env vars that look like tokens/passwords
                result[k] = {}
                for ek, ev in v.items():
                    if SECRET_PATTERNS.search(ek) or (
                        isinstance(ev, str) and len(ev) > 20
                    ):
                        result[k][ek] = "***REDACTED***"
                    else:
                        result[k][ek] = ev
            else:
                result[k] = redact_secrets(v, k)
        return result
    elif isinstance(obj, list):
        return [redact_secrets(item, parent_key) for item in obj]
    return obj


def get_memory_files():
    """List memory .md files."""
    if not MEMORY_DIR.exists():
        return []
    files = []
    for f in sorted(MEMORY_DIR.glob("*.md")):
        files.append({"name": f.name, "path": str(f)})
    return files


def load_plan_config():
    """Load plan configuration."""
    if PLAN_CONFIG_FILE.exists():
        try:
            return json.loads(PLAN_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return dict(DEFAULT_PLAN)


def save_plan_config(config):
    """Save plan configuration."""
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    PLAN_CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")


def get_current_period_token_usage():
    """Get total token usage for the current billing period from subagent transcripts."""
    plan = load_plan_config()
    billing_start = plan.get("billingCycleStart", "")

    all_usage = get_subagent_token_usage()

    period_total = 0
    period_output = 0
    period_input = 0
    period_agents = 0

    for agent_data in all_usage.values():
        # If billing cycle is set, only count agents from that period
        if billing_start and agent_data.get("startTime", "") < billing_start:
            continue
        period_total += agent_data["totalTokens"]
        period_input += agent_data["inputTokens"] + agent_data["cacheReadTokens"] + agent_data["cacheCreateTokens"]
        period_output += agent_data["outputTokens"]
        period_agents += 1

    limit = plan.get("monthlyTokenLimit", 0)
    pct = round((period_total / limit) * 100, 1) if limit > 0 else 0

    return {
        "periodTotal": period_total,
        "periodInput": period_input,
        "periodOutput": period_output,
        "periodAgents": period_agents,
        "limit": limit,
        "usagePercent": pct,
        "plan": plan,
    }


def get_subagent_token_usage():
    """Scan all subagent transcripts under ~/.claude/projects/ for real token usage.
    Returns a dict keyed by agentId with token counts and prompt snippet for matching.
    Results are cached for TOKEN_CACHE_TTL seconds to avoid slow re-scans."""
    global _token_usage_cache
    now = time.time()
    if _token_usage_cache["data"] is not None and (now - _token_usage_cache["timestamp"]) < TOKEN_CACHE_TTL:
        return _token_usage_cache["data"]

    usage_by_agent = {}
    try:
        for project_dir in PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue
            project_name = project_dir.name
            for session_dir in project_dir.iterdir():
                subagents_dir = session_dir / "subagents" if session_dir.is_dir() else None
                if not subagents_dir or not subagents_dir.exists():
                    continue
                for transcript in subagents_dir.glob("agent-*.jsonl"):
                    agent_id = transcript.stem  # e.g. "agent-af7c649862eeabf3a"
                    total_input = 0
                    total_output = 0
                    total_cache_read = 0
                    total_cache_create = 0
                    api_calls = 0
                    prompt_snippet = ""
                    agent_start_time = ""

                    with open(transcript, "r") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                d = json.loads(line)
                            except json.JSONDecodeError:
                                continue

                            dtype = d.get("type")

                            if dtype == "user" and not prompt_snippet:
                                msg = d.get("message", {})
                                agent_start_time = d.get("timestamp", "")
                                content = msg.get("content", "") if isinstance(msg, dict) else ""
                                if isinstance(content, str):
                                    prompt_snippet = content[:120]
                                elif isinstance(content, list):
                                    for c in content:
                                        if isinstance(c, dict) and c.get("type") == "text":
                                            prompt_snippet = c.get("text", "")[:120]
                                            break

                            elif dtype == "assistant":
                                msg = d.get("message")
                                if isinstance(msg, dict):
                                    u = msg.get("usage")
                                    if u:
                                        total_input += u.get("input_tokens", 0)
                                        total_cache_create += u.get("cache_creation_input_tokens", 0)
                                        total_cache_read += u.get("cache_read_input_tokens", 0)
                                        total_output += u.get("output_tokens", 0)
                                        api_calls += 1

                    usage_by_agent[agent_id] = {
                        "agentId": agent_id,
                        "project": project_name,
                        "inputTokens": total_input,
                        "outputTokens": total_output,
                        "cacheReadTokens": total_cache_read,
                        "cacheCreateTokens": total_cache_create,
                        "totalTokens": total_input + total_output + total_cache_read + total_cache_create,
                        "apiCalls": api_calls,
                        "promptSnippet": prompt_snippet,
                        "startTime": agent_start_time,
                        "session": session_dir.name,
                    }
    except Exception:
        pass

    _token_usage_cache["data"] = usage_by_agent
    _token_usage_cache["timestamp"] = now
    return usage_by_agent


def get_sessions_with_agents():
    """List sessions grouped with their subagents and token stats for context-reuse decisions."""
    sessions = {}
    try:
        for project_dir in PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue
            project_name = project_dir.name
            for session_entry in project_dir.iterdir():
                # Session transcripts are .jsonl files at project level
                if session_entry.suffix == ".jsonl" and session_entry.is_file():
                    session_id = session_entry.stem
                    subagents_dir = project_dir / session_id / "subagents"

                    # Get session start time and first user message
                    session_prompt = ""
                    session_time = ""
                    try:
                        with open(session_entry, "r") as f:
                            for line in f:
                                d = json.loads(line.strip())
                                if d.get("type") == "user" and not session_prompt:
                                    session_time = d.get("timestamp", "")
                                    msg = d.get("message", {})
                                    content = msg.get("content", "") if isinstance(msg, dict) else ""
                                    if isinstance(content, str):
                                        session_prompt = content[:100]
                                    elif isinstance(content, list):
                                        for c in content:
                                            if isinstance(c, dict) and c.get("type") == "text":
                                                session_prompt = c.get("text", "")[:100]
                                                break
                                    break
                    except Exception:
                        pass

                    # Count subagents
                    agent_count = 0
                    total_cache_create = 0
                    if subagents_dir and subagents_dir.exists():
                        for t in subagents_dir.glob("agent-*.jsonl"):
                            agent_count += 1
                            try:
                                with open(t) as f:
                                    for line in f:
                                        d = json.loads(line.strip())
                                        if d.get("type") == "assistant":
                                            msg = d.get("message", {})
                                            if isinstance(msg, dict):
                                                u = msg.get("usage", {})
                                                total_cache_create += u.get("cache_creation_input_tokens", 0)
                            except Exception:
                                pass

                    sessions[session_id] = {
                        "sessionId": session_id,
                        "project": project_name,
                        "prompt": session_prompt,
                        "startTime": session_time,
                        "agentCount": agent_count,
                        "cacheCreated": total_cache_create,
                    }
    except Exception:
        pass
    return sessions


def get_agent_prompt(agent_id):
    """Extract the full original prompt from a subagent transcript."""
    try:
        for project_dir in PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue
            for session_dir in project_dir.iterdir():
                if not session_dir.is_dir():
                    continue
                transcript = session_dir / "subagents" / f"{agent_id}.jsonl"
                if not transcript.exists():
                    continue
                with open(transcript, "r") as f:
                    for line in f:
                        try:
                            d = json.loads(line.strip())
                        except json.JSONDecodeError:
                            continue
                        if d.get("type") == "user":
                            msg = d.get("message", {})
                            content = msg.get("content", "") if isinstance(msg, dict) else ""
                            if isinstance(content, str):
                                return content, None
                            elif isinstance(content, list):
                                texts = []
                                for c in content:
                                    if isinstance(c, dict) and c.get("type") == "text":
                                        texts.append(c.get("text", ""))
                                return "\n".join(texts), None
    except Exception as e:
        return None, str(e)
    return None, "Agent transcript not found"


def read_file_safe(filepath):
    """Read a file, only if it's under ~/.claude/."""
    path = Path(filepath).resolve()
    claude_resolved = CLAUDE_DIR.resolve()
    if not str(path).startswith(str(claude_resolved)):
        return None, "Access denied: path must be under ~/.claude/"
    if not path.exists():
        return None, "File not found"
    try:
        content = path.read_text(encoding="utf-8")
        return content, None
    except Exception as e:
        return None, str(e)


def delete_memory_file(filename):
    """Delete a memory file and remove its entry from MEMORY.md index."""
    if not filename.endswith(".md"):
        return False, "Only .md files can be deleted"
    # Prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        return False, "Invalid filename"
    if filename == "MEMORY.md":
        return False, "Cannot delete the MEMORY.md index file"

    filepath = MEMORY_DIR / filename
    if not filepath.exists():
        return False, "File not found"

    try:
        filepath.unlink()

        # Remove reference from MEMORY.md index
        index_file = MEMORY_DIR / "MEMORY.md"
        if index_file.exists():
            lines = index_file.read_text(encoding="utf-8").splitlines()
            # Filter out lines that reference the deleted file
            base = filename.replace(".md", "")
            new_lines = [
                line for line in lines
                if filename not in line and f"]({filename})" not in line
                and f"({base})" not in line
            ]
            index_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

        return True, None
    except Exception as e:
        return False, str(e)


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            with open(DASHBOARD_FILE, "rb") as f:
                self.wfile.write(f.read())

        elif path == "/status":
            state = build_state_from_events()
            # Include cached token usage if available (don't trigger scan from polling)
            if _token_usage_cache["data"] is not None:
                period = get_current_period_token_usage()
                state["tokenUsage"] = {
                    "totalInputTokens": period["periodInput"],
                    "totalOutputTokens": period["periodOutput"],
                    "totalTokens": period["periodTotal"],
                    "periodAgents": period["periodAgents"],
                    "limit": period["limit"],
                    "usagePercent": period["usagePercent"],
                    "plan": period["plan"],
                }
            self._json_response(state)

        elif path == "/reset":
            STATUS_DIR.mkdir(parents=True, exist_ok=True)
            if EVENTS_FILE.exists():
                EVENTS_FILE.unlink()
            self._json_response({"ok": True})

        elif path == "/api/agents":
            self._json_response(get_custom_agents())

        elif path == "/api/skills":
            self._json_response(get_skills())

        elif path == "/api/plugins":
            self._json_response(get_plugins())

        elif path == "/api/settings":
            self._json_response(get_settings())

        elif path == "/api/memory":
            self._json_response(get_memory_files())

        elif path == "/api/file":
            filepath = params.get("path", [None])[0]
            if not filepath:
                self._json_response({"error": "Missing path parameter"}, 400)
                return
            content, error = read_file_safe(filepath)
            if error:
                self._json_response({"error": error}, 403)
            else:
                self._json_response({"content": content})

        elif path == "/api/plan":
            self._json_response(load_plan_config())

        elif path == "/api/token-usage":
            # Force refresh if requested
            if params.get("refresh", [""])[0] == "1":
                _token_usage_cache["data"] = None
                _token_usage_cache["timestamp"] = 0
            usage = get_subagent_token_usage()
            # Sort by total tokens descending
            agents_list = sorted(usage.values(), key=lambda x: x["totalTokens"], reverse=True)
            total = {
                "totalInputTokens": sum(a["inputTokens"] for a in agents_list),
                "totalOutputTokens": sum(a["outputTokens"] for a in agents_list),
                "totalCacheRead": sum(a["cacheReadTokens"] for a in agents_list),
                "totalCacheCreate": sum(a["cacheCreateTokens"] for a in agents_list),
                "totalTokens": sum(a["totalTokens"] for a in agents_list),
                "totalApiCalls": sum(a["apiCalls"] for a in agents_list),
                "agentCount": len(agents_list),
            }
            self._json_response({"agents": agents_list, "total": total})

        elif path == "/api/sessions":
            sessions = get_sessions_with_agents()
            # Sort by start time descending, limit to recent
            sessions_list = sorted(
                sessions.values(),
                key=lambda x: x.get("startTime", ""),
                reverse=True,
            )[:50]
            self._json_response(sessions_list)

        elif path == "/api/agent-prompt":
            agent_id = params.get("id", [None])[0]
            if not agent_id:
                self._json_response({"error": "Missing id parameter"}, 400)
            else:
                prompt, error = get_agent_prompt(agent_id)
                if error:
                    self._json_response({"error": error}, 404)
                else:
                    self._json_response({"agentId": agent_id, "prompt": prompt})

        elif path == "/api/agent-events":
            # Get events for a specific agent by description
            desc = params.get("desc", [None])[0]
            if not desc:
                self._json_response({"error": "Missing desc parameter"}, 400)
                return
            state = build_state_from_events()
            agent_logs = [e for e in state["log"] if desc.lower() in (e.get("agent", "") + " " + e.get("message", "")).lower()]
            self._json_response({"events": agent_logs})

        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/api/memory":
            filename = params.get("file", [None])[0]
            if not filename:
                self._json_response({"error": "Missing file parameter"}, 400)
                return
            ok, error = delete_memory_file(filename)
            if error:
                self._json_response({"error": error}, 400)
            else:
                self._json_response({"ok": True, "deleted": filename})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        if path == "/api/plan":
            try:
                data = json.loads(body) if body else {}
                config = load_plan_config()
                if "name" in data:
                    config["name"] = data["name"]
                if "monthlyTokenLimit" in data:
                    config["monthlyTokenLimit"] = int(data["monthlyTokenLimit"])
                if "billingCycleStart" in data:
                    config["billingCycleStart"] = data["billingCycleStart"]
                save_plan_config(config)
                self._json_response({"ok": True, "config": config})
            except Exception as e:
                self._json_response({"error": str(e)}, 400)

        elif path == "/api/agent-rerun":
            try:
                data = json.loads(body) if body else {}
                prompt = data.get("prompt", "")
                model = data.get("model", "")
                name = data.get("name", "rerun")
                session_id = data.get("sessionId", "")  # resume existing session
                if not prompt:
                    self._json_response({"error": "Missing prompt"}, 400)
                    return

                # Write prompt to temp file to avoid shell escaping issues
                import tempfile
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False, dir="/tmp"
                ) as tmp:
                    tmp.write(prompt)
                    prompt_file = tmp.name

                if session_id:
                    # Continue existing session — reuses cached context (saves tokens!)
                    cmd = f'claude --resume {session_id} --fork-session -p "$(cat {prompt_file})" --output-format json'
                else:
                    cmd = f'claude -p "$(cat {prompt_file})" --output-format json'

                if model:
                    cmd += f" --model {model}"
                cmd += f' --name "{name}"'
                cmd += f" && rm -f {prompt_file}"

                # Run in background
                log_file = f"/tmp/agent-dashboard/rerun-{int(time.time())}.log"
                full_cmd = f"nohup bash -c '{cmd}' > {log_file} 2>&1 &"
                subprocess.Popen(
                    full_cmd, shell=True, cwd=str(Path.home()),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                mode = "continued (reusing cache)" if session_id else "new session"
                self._json_response({
                    "ok": True,
                    "message": f"Agent started in background ({mode})",
                    "logFile": log_file,
                    "mode": mode,
                })
            except Exception as e:
                self._json_response({"error": str(e)}, 500)

        elif path == "/api/exec":
            try:
                data = json.loads(body) if body else {}
                command = data.get("command", "")
                cwd = data.get("cwd", os.path.expanduser("~"))

                if not command:
                    self._json_response({"error": "Missing command"}, 400)
                    return

                # Run command with timeout
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=cwd,
                    env={**os.environ, "TERM": "dumb"},
                )
                self._json_response({
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                })
            except subprocess.TimeoutExpired:
                self._json_response({"error": "Command timed out (30s)", "stdout": "", "stderr": "", "returncode": -1})
            except Exception as e:
                self._json_response({"error": str(e)}, 500)
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        pass


def main():
    port = PORT
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--port" and i + 2 <= len(sys.argv):
            port = int(sys.argv[i + 2])

    STATUS_DIR.mkdir(parents=True, exist_ok=True)

    class ReusableHTTPServer(http.server.HTTPServer):
        allow_reuse_address = True
        allow_reuse_port = True

    server = ReusableHTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"\033[1;36m  Agent Dashboard\033[0m")
    print(f"  http://localhost:{port}")
    print(f"  Events: {EVENTS_FILE}")
    print(f"  Tracking: ALL agents (universal)")
    print(f"  API: /api/skills, /api/plugins, /api/settings, /api/memory, /api/file")
    print(f"  Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
        server.server_close()


if __name__ == "__main__":
    main()

#!/usr/bin/env bash
#
# Claude Code Sync Setup
#
# Run this on any device to sync your agents, skills, hooks, and dashboard.
# It creates symlinks from ~/.claude/ to this repo so everything stays in git.
#
# Usage:
#   git clone <your-repo> ~/IdeaProjects/tools
#   cd ~/IdeaProjects/tools/claude-sync
#   ./setup.sh
#
# What it does:
#   1. Symlinks agents   (this repo → ~/.claude/agents/)
#   2. Symlinks skills   (this repo → ~/.claude/skills/)
#   3. Sets up dashboard hooks in settings.json
#   4. Installs dashboard auto-start
#
# Safe: backs up existing files before overwriting.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOLS_DIR="$(dirname "$SCRIPT_DIR")"
CLAUDE_DIR="$HOME/.claude"
BACKUP_DIR="$CLAUDE_DIR/backup-$(date +%Y%m%d-%H%M%S)"

echo ""
echo "  Claude Code Sync Setup"
echo "  Repo: $SCRIPT_DIR"
echo "  Target: $CLAUDE_DIR"
echo ""

# Ensure ~/.claude exists
mkdir -p "$CLAUDE_DIR"

# ===== 1. AGENTS =====
echo "[1/4] Syncing agents..."
if [ -d "$CLAUDE_DIR/agents" ] && [ ! -L "$CLAUDE_DIR/agents" ]; then
    echo "  Backing up existing agents to $BACKUP_DIR/agents/"
    mkdir -p "$BACKUP_DIR"
    mv "$CLAUDE_DIR/agents" "$BACKUP_DIR/agents"
fi

if [ -L "$CLAUDE_DIR/agents" ]; then
    current_target=$(readlink "$CLAUDE_DIR/agents")
    if [ "$current_target" = "$SCRIPT_DIR/agents" ]; then
        echo "  Already linked. Skipping."
    else
        echo "  Updating symlink (was: $current_target)"
        rm "$CLAUDE_DIR/agents"
        ln -s "$SCRIPT_DIR/agents" "$CLAUDE_DIR/agents"
    fi
else
    ln -s "$SCRIPT_DIR/agents" "$CLAUDE_DIR/agents"
    echo "  Linked: ~/.claude/agents -> $SCRIPT_DIR/agents"
fi

# ===== 2. SKILLS =====
echo "[2/4] Syncing skills..."
mkdir -p "$CLAUDE_DIR/skills"

for skill_dir in "$SCRIPT_DIR/skills"/*/; do
    skill_name=$(basename "$skill_dir")
    target="$CLAUDE_DIR/skills/$skill_name"

    if [ -d "$target" ] && [ ! -L "$target" ]; then
        echo "  Backing up existing skill: $skill_name"
        mkdir -p "$BACKUP_DIR/skills"
        mv "$target" "$BACKUP_DIR/skills/$skill_name"
    fi

    if [ -L "$target" ]; then
        current_target=$(readlink "$target")
        if [ "$current_target" = "$skill_dir" ] || [ "$current_target" = "${skill_dir%/}" ]; then
            echo "  $skill_name: already linked. Skipping."
            continue
        fi
        rm "$target"
    fi

    ln -s "${skill_dir%/}" "$target"
    echo "  $skill_name: linked"
done

# ===== 3. DASHBOARD HOOKS =====
echo "[3/4] Checking dashboard hooks..."
DASHBOARD_DIR="$TOOLS_DIR/agent-dashboard"

if [ ! -f "$DASHBOARD_DIR/hook-agent-start.sh" ]; then
    echo "  Dashboard not found at $DASHBOARD_DIR. Skipping hooks."
else
    # Check if hooks are already configured
    if [ -f "$CLAUDE_DIR/settings.json" ]; then
        if grep -q "hook-agent-start.sh" "$CLAUDE_DIR/settings.json" 2>/dev/null; then
            # Update paths if they point to a different location
            CURRENT_PATH=$(python3 -c "
import json
with open('$CLAUDE_DIR/settings.json') as f:
    d = json.load(f)
hooks = d.get('hooks',{}).get('PreToolUse',[])
for h in hooks:
    for hh in h.get('hooks',[]):
        cmd = hh.get('command','')
        if 'hook-agent-start' in cmd:
            print(cmd)
            break
" 2>/dev/null)
            if [ "$CURRENT_PATH" = "$DASHBOARD_DIR/hook-agent-start.sh" ]; then
                echo "  Hooks already configured. Skipping."
            else
                echo "  Updating hook paths to $DASHBOARD_DIR/"
                python3 -c "
import json
with open('$CLAUDE_DIR/settings.json') as f:
    d = json.load(f)
for event_type in ['PreToolUse', 'PostToolUse']:
    for h in d.get('hooks',{}).get(event_type,[]):
        for hh in h.get('hooks',[]):
            cmd = hh.get('command','')
            if 'hook-agent-start' in cmd:
                hh['command'] = '$DASHBOARD_DIR/hook-agent-start.sh'
            elif 'hook-agent-end' in cmd:
                hh['command'] = '$DASHBOARD_DIR/hook-agent-end.sh'
with open('$CLAUDE_DIR/settings.json','w') as f:
    json.dump(d, f, indent=2)
print('  Hook paths updated.')
"
            fi
        else
            echo "  No dashboard hooks found. Adding them..."
            python3 -c "
import json
with open('$CLAUDE_DIR/settings.json') as f:
    d = json.load(f)
d.setdefault('hooks', {})
d['hooks']['PreToolUse'] = d['hooks'].get('PreToolUse', []) + [{
    'matcher': 'Agent',
    'hooks': [{'type': 'command', 'command': '$DASHBOARD_DIR/hook-agent-start.sh', 'timeout': 10, 'async': True}]
}]
d['hooks']['PostToolUse'] = d['hooks'].get('PostToolUse', []) + [{
    'matcher': 'Agent',
    'hooks': [{'type': 'command', 'command': '$DASHBOARD_DIR/hook-agent-end.sh', 'timeout': 10, 'async': True}]
}]
with open('$CLAUDE_DIR/settings.json','w') as f:
    json.dump(d, f, indent=2)
print('  Hooks added.')
"
        fi
    else
        echo "  No settings.json found. Creating with hooks..."
        python3 -c "
import json
d = {
    'hooks': {
        'PreToolUse': [{'matcher': 'Agent', 'hooks': [{'type': 'command', 'command': '$DASHBOARD_DIR/hook-agent-start.sh', 'timeout': 10, 'async': True}]}],
        'PostToolUse': [{'matcher': 'Agent', 'hooks': [{'type': 'command', 'command': '$DASHBOARD_DIR/hook-agent-end.sh', 'timeout': 10, 'async': True}]}]
    }
}
with open('$CLAUDE_DIR/settings.json','w') as f:
    json.dump(d, f, indent=2)
print('  settings.json created with hooks.')
"
    fi
fi

# ===== 4. PLUGINS =====
echo "[4/5] Syncing plugins..."
PLUGINS_MANIFEST="$SCRIPT_DIR/plugins.json"

if [ ! -f "$PLUGINS_MANIFEST" ]; then
    echo "  No plugins.json found. Skipping."
else
    if ! command -v claude &>/dev/null; then
        echo "  'claude' CLI not found. Install Claude Code first, then re-run."
    else
        # Add marketplaces
        python3 -c "
import json, subprocess, sys
with open('$PLUGINS_MANIFEST') as f:
    manifest = json.load(f)

# Check existing marketplaces
result = subprocess.run(['claude', 'plugins', 'marketplace', 'list'], capture_output=True, text=True)
existing = result.stdout

for mp in manifest.get('marketplaces', []):
    name = mp['name']
    source = mp['source']
    if name in existing:
        print(f'  Marketplace {name}: already added')
    else:
        print(f'  Adding marketplace: {name} ({source})')
        r = subprocess.run(['claude', 'plugins', 'marketplace', 'add', source], capture_output=True, text=True)
        if r.returncode == 0:
            print(f'  Marketplace {name}: added')
        else:
            print(f'  Marketplace {name}: failed - {r.stderr.strip()[:100]}')

# Install plugins
result = subprocess.run(['claude', 'plugins', 'list'], capture_output=True, text=True)
installed = result.stdout

for plugin in manifest.get('plugins', []):
    if plugin in installed:
        print(f'  Plugin {plugin}: already installed')
    else:
        print(f'  Installing plugin: {plugin}')
        r = subprocess.run(['claude', 'plugins', 'install', plugin], capture_output=True, text=True)
        if r.returncode == 0:
            print(f'  Plugin {plugin}: installed')
        else:
            print(f'  Plugin {plugin}: failed - {r.stderr.strip()[:100]}')
"
    fi
fi

# ===== 5. SUMMARY =====
echo "[5/5] Done!"
echo ""
echo "  Synced to this device:"
echo "  ----------------------"
PLUGIN_COUNT=$(python3 -c "import json; print(len(json.load(open('$PLUGINS_MANIFEST')).get('plugins',[])))" 2>/dev/null || echo "0")
echo "  Agents:    $(ls "$SCRIPT_DIR/agents/"*.md 2>/dev/null | wc -l | tr -d ' ') files"
echo "  Skills:    $(ls -d "$SCRIPT_DIR/skills"/*/ 2>/dev/null | wc -l | tr -d ' ') skills"
echo "  Plugins:   $PLUGIN_COUNT plugins"
echo "  Dashboard: $DASHBOARD_DIR"
echo ""
echo "  To add a new agent:   Create $SCRIPT_DIR/agents/my-agent.md"
echo "  To add a new skill:   Create $SCRIPT_DIR/skills/my-skill/SKILL.md"
echo "  To add a new plugin:  Add to $SCRIPT_DIR/plugins.json"
echo "  Then: git add, commit, push, and run ./setup.sh on other devices."
echo ""
if [ -d "$BACKUP_DIR" ]; then
    echo "  Backup: $BACKUP_DIR"
    echo ""
fi

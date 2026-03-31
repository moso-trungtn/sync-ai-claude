#!/bin/bash
# Setup script: symlinks .claude/agents and .claude/skills to ~/.claude/
# Run this after cloning on a new device.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$SCRIPT_DIR/.claude"
USER_CLAUDE="$HOME/.claude"

mkdir -p "$USER_CLAUDE"

# Backup and replace agents
if [ -d "$USER_CLAUDE/agents" ] && [ ! -L "$USER_CLAUDE/agents" ]; then
    BACKUP="$USER_CLAUDE/backup-agents-$(date +%Y%m%d%H%M%S)"
    echo "Backing up existing agents to $BACKUP"
    mv "$USER_CLAUDE/agents" "$BACKUP"
fi
rm -f "$USER_CLAUDE/agents"
ln -s "$CLAUDE_DIR/agents" "$USER_CLAUDE/agents"
echo "Linked: ~/.claude/agents -> $CLAUDE_DIR/agents"

# Backup and replace skills
if [ -d "$USER_CLAUDE/skills" ] && [ ! -L "$USER_CLAUDE/skills" ]; then
    BACKUP="$USER_CLAUDE/backup-skills-$(date +%Y%m%d%H%M%S)"
    echo "Backing up existing skills to $BACKUP"
    mv "$USER_CLAUDE/skills" "$BACKUP"
fi
rm -f "$USER_CLAUDE/skills"
ln -s "$CLAUDE_DIR/skills" "$USER_CLAUDE/skills"
echo "Linked: ~/.claude/skills -> $CLAUDE_DIR/skills"

echo ""
echo "Done! Restart Claude Code to pick up agents and skills."

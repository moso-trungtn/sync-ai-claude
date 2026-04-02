#!/bin/bash
# Setup script: symlinks agents + skills, restores knowledge to project memory.
# Run this after cloning on a new device.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$SCRIPT_DIR/.claude"
USER_CLAUDE="$HOME/.claude"

mkdir -p "$USER_CLAUDE"

echo "=== Setting up Claude Code agents, skills & knowledge ==="
echo ""

# --- Agents ---
if [ -d "$USER_CLAUDE/agents" ] && [ ! -L "$USER_CLAUDE/agents" ]; then
    BACKUP="$USER_CLAUDE/backup-agents-$(date +%Y%m%d%H%M%S)"
    echo "Backing up existing agents to $BACKUP"
    mv "$USER_CLAUDE/agents" "$BACKUP"
fi
rm -f "$USER_CLAUDE/agents"
ln -s "$CLAUDE_DIR/agents" "$USER_CLAUDE/agents"
echo "✓ Linked: ~/.claude/agents -> $CLAUDE_DIR/agents"

# --- Skills ---
if [ -d "$USER_CLAUDE/skills" ] && [ ! -L "$USER_CLAUDE/skills" ]; then
    BACKUP="$USER_CLAUDE/backup-skills-$(date +%Y%m%d%H%M%S)"
    echo "Backing up existing skills to $BACKUP"
    mv "$USER_CLAUDE/skills" "$BACKUP"
fi
rm -f "$USER_CLAUDE/skills"
ln -s "$CLAUDE_DIR/skills" "$USER_CLAUDE/skills"
echo "✓ Linked: ~/.claude/skills -> $CLAUDE_DIR/skills"

# --- Knowledge → Project Memory ---
# Detect project memory dir (based on workspace path)
WORKSPACE_PATH="$(cd "$SCRIPT_DIR/.." && pwd)"
# Claude Code encodes paths by replacing / with -
ENCODED_PATH=$(echo "$WORKSPACE_PATH" | sed 's|^/|-|; s|/|-|g')
MEMORY_DIR="$USER_CLAUDE/projects/$ENCODED_PATH/memory"

if [ -d "$CLAUDE_DIR/knowledge" ]; then
    mkdir -p "$MEMORY_DIR"
    RESTORED=0
    for f in "$CLAUDE_DIR/knowledge"/*.md; do
        if [ -f "$f" ]; then
            fname=$(basename "$f")
            if [ ! -f "$MEMORY_DIR/$fname" ]; then
                cp "$f" "$MEMORY_DIR/$fname"
                echo "✓ Restored: knowledge/$fname -> project memory"
                RESTORED=$((RESTORED + 1))
            else
                # Only restore if repo version is newer (larger file = more knowledge)
                REPO_SIZE=$(wc -c < "$f")
                LOCAL_SIZE=$(wc -c < "$MEMORY_DIR/$fname")
                if [ "$REPO_SIZE" -gt "$LOCAL_SIZE" ]; then
                    cp "$f" "$MEMORY_DIR/$fname"
                    echo "✓ Updated: knowledge/$fname (repo has more knowledge)"
                    RESTORED=$((RESTORED + 1))
                else
                    echo "  Skipped: knowledge/$fname (local is up to date)"
                fi
            fi
        fi
    done
    echo "✓ Knowledge: $RESTORED files restored to project memory"
else
    echo "  No knowledge directory found (first-time setup)"
fi

echo ""
echo "Done! Restart Claude Code to pick up agents, skills, and knowledge."
echo ""
echo "Agents:    $(ls "$CLAUDE_DIR/agents"/*.md 2>/dev/null | wc -l | tr -d ' ') files"
echo "Skills:    $(ls -d "$CLAUDE_DIR/skills"/*/ 2>/dev/null | wc -l | tr -d ' ') directories"
echo "Knowledge: $(ls "$CLAUDE_DIR/knowledge"/*.md 2>/dev/null | wc -l | tr -d ' ') files"

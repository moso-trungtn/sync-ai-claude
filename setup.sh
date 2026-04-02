#!/bin/bash
# Setup script: merges agents, skills, and knowledge from repo into ~/.claude.
# Existing local files are NEVER overwritten or deleted — repo files are added alongside them.
# Run this after cloning on a new device.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$SCRIPT_DIR/.claude"
USER_CLAUDE="$HOME/.claude"

mkdir -p "$USER_CLAUDE"

echo "=== Setting up Claude Code agents, skills & knowledge ==="
echo ""

# --- Agents (merge, not replace) ---
echo "--- Agents ---"
mkdir -p "$USER_CLAUDE/agents"

# If agents is currently a symlink, convert to a real directory first
if [ -L "$USER_CLAUDE/agents" ]; then
    TARGET=$(readlink "$USER_CLAUDE/agents")
    rm "$USER_CLAUDE/agents"
    mkdir -p "$USER_CLAUDE/agents"
    cp "$TARGET"/*.md "$USER_CLAUDE/agents/" 2>/dev/null
    echo "  Converted symlink to real directory"
fi

ADDED=0
UPDATED=0
SKIPPED=0
for f in "$CLAUDE_DIR/agents"/*.md; do
    [ -f "$f" ] || continue
    fname=$(basename "$f")
    if [ ! -f "$USER_CLAUDE/agents/$fname" ]; then
        cp "$f" "$USER_CLAUDE/agents/$fname"
        echo "  NEW: agents/$fname"
        ADDED=$((ADDED + 1))
    elif ! diff -q "$f" "$USER_CLAUDE/agents/$fname" > /dev/null 2>&1; then
        cp "$f" "$USER_CLAUDE/agents/$fname"
        echo "  UPDATED: agents/$fname"
        UPDATED=$((UPDATED + 1))
    else
        SKIPPED=$((SKIPPED + 1))
    fi
done
echo "✓ Agents: $ADDED new, $UPDATED updated, $SKIPPED unchanged"
echo ""

# --- Skills (merge, not replace) ---
echo "--- Skills ---"
mkdir -p "$USER_CLAUDE/skills"

# If skills is currently a symlink, convert to a real directory first
if [ -L "$USER_CLAUDE/skills" ]; then
    TARGET=$(readlink "$USER_CLAUDE/skills")
    rm "$USER_CLAUDE/skills"
    mkdir -p "$USER_CLAUDE/skills"
    cp -r "$TARGET"/*/ "$USER_CLAUDE/skills/" 2>/dev/null
    echo "  Converted symlink to real directory"
fi

ADDED=0
UPDATED=0
SKIPPED=0
for d in "$CLAUDE_DIR/skills"/*/; do
    [ -d "$d" ] || continue
    skill=$(basename "$d")
    if [ ! -d "$USER_CLAUDE/skills/$skill" ]; then
        cp -r "$d" "$USER_CLAUDE/skills/$skill"
        echo "  NEW: skills/$skill"
        ADDED=$((ADDED + 1))
    elif [ -f "$d/SKILL.md" ] && [ -f "$USER_CLAUDE/skills/$skill/SKILL.md" ]; then
        if ! diff -q "$d/SKILL.md" "$USER_CLAUDE/skills/$skill/SKILL.md" > /dev/null 2>&1; then
            cp -r "$d"/* "$USER_CLAUDE/skills/$skill/"
            echo "  UPDATED: skills/$skill"
            UPDATED=$((UPDATED + 1))
        else
            SKIPPED=$((SKIPPED + 1))
        fi
    else
        SKIPPED=$((SKIPPED + 1))
    fi
done
echo "✓ Skills: $ADDED new, $UPDATED updated, $SKIPPED unchanged"
echo ""

# --- Knowledge → Project Memory (merge, not replace) ---
echo "--- Knowledge ---"
WORKSPACE_PATH="$(cd "$SCRIPT_DIR/.." && pwd)"
ENCODED_PATH=$(echo "$WORKSPACE_PATH" | sed 's|^/|-|; s|/|-|g')
MEMORY_DIR="$USER_CLAUDE/projects/$ENCODED_PATH/memory"
mkdir -p "$MEMORY_DIR"

ADDED=0
UPDATED=0
SKIPPED=0
if [ -d "$CLAUDE_DIR/knowledge" ]; then
    for f in "$CLAUDE_DIR/knowledge"/*.md; do
        [ -f "$f" ] || continue
        fname=$(basename "$f")
        if [ ! -f "$MEMORY_DIR/$fname" ]; then
            cp "$f" "$MEMORY_DIR/$fname"
            echo "  NEW: knowledge/$fname"
            ADDED=$((ADDED + 1))
        else
            REPO_SIZE=$(wc -c < "$f")
            LOCAL_SIZE=$(wc -c < "$MEMORY_DIR/$fname")
            if [ "$REPO_SIZE" -gt "$LOCAL_SIZE" ]; then
                cp "$f" "$MEMORY_DIR/$fname"
                echo "  UPDATED: knowledge/$fname (repo has newer content)"
                UPDATED=$((UPDATED + 1))
            else
                SKIPPED=$((SKIPPED + 1))
            fi
        fi
    done
fi
echo "✓ Knowledge: $ADDED new, $UPDATED updated, $SKIPPED unchanged"
echo ""

# --- Summary ---
echo "=== Done! ==="
echo ""
echo "Agents:    $(ls "$USER_CLAUDE/agents"/*.md 2>/dev/null | wc -l | tr -d ' ') files"
echo "Skills:    $(ls -d "$USER_CLAUDE/skills"/*/ 2>/dev/null | wc -l | tr -d ' ') directories"
echo "Knowledge: $(ls "$MEMORY_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ') files"
echo ""
echo "Your existing agents/skills were preserved. Only new or updated files were added."
echo "Restart Claude Code to pick up changes."

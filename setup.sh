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

# ─── Detect shell profile ───
if [ -n "$ZSH_VERSION" ] || [ -f "$HOME/.zshrc" ]; then
    SHELL_PROFILE="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_PROFILE="$HOME/.bashrc"
elif [ -f "$HOME/.bash_profile" ]; then
    SHELL_PROFILE="$HOME/.bash_profile"
else
    SHELL_PROFILE="$HOME/.profile"
fi

# ─── Environment configuration ───
echo "--- Environment ---"

NEEDS_ENV=false

# Check JIRA_EMAIL
if [ -z "$JIRA_EMAIL" ] && ! grep -q 'export JIRA_EMAIL=' "$SHELL_PROFILE" 2>/dev/null; then
    NEEDS_ENV=true
fi

# Check JIRA_API_TOKEN
if [ -z "$JIRA_API_TOKEN" ] && ! grep -q 'export JIRA_API_TOKEN=' "$SHELL_PROFILE" 2>/dev/null; then
    NEEDS_ENV=true
fi

if [ "$NEEDS_ENV" = true ]; then
    echo ""
    echo "  Some environment variables are not configured yet."
    echo "  These are needed for /fix-parser, /new-parser, and /tera skills."
    echo ""
    printf "  Configure now? [Y/n] "
    read -r CONFIGURE_ENV
    CONFIGURE_ENV="${CONFIGURE_ENV:-Y}"

    if [[ "$CONFIGURE_ENV" =~ ^[Yy]$ ]]; then
        # ── JIRA_EMAIL ──
        if [ -z "$JIRA_EMAIL" ] && ! grep -q 'export JIRA_EMAIL=' "$SHELL_PROFILE" 2>/dev/null; then
            printf "  Jira email (e.g., name@loanfactory.com): "
            read -r INPUT_JIRA_EMAIL
            if [ -n "$INPUT_JIRA_EMAIL" ]; then
                echo "" >> "$SHELL_PROFILE"
                echo "# Claude Code — Jira integration" >> "$SHELL_PROFILE"
                echo "export JIRA_EMAIL=\"$INPUT_JIRA_EMAIL\"" >> "$SHELL_PROFILE"
                export JIRA_EMAIL="$INPUT_JIRA_EMAIL"
                echo "  ✓ JIRA_EMAIL saved to $SHELL_PROFILE"
            else
                echo "  ⊘ Skipped JIRA_EMAIL"
            fi
        else
            echo "  ✓ JIRA_EMAIL already set"
        fi

        # ── JIRA_API_TOKEN ──
        if [ -z "$JIRA_API_TOKEN" ] && ! grep -q 'export JIRA_API_TOKEN=' "$SHELL_PROFILE" 2>/dev/null; then
            echo ""
            echo "  Get your API token from: https://id.atlassian.com/manage-profile/security/api-tokens"
            printf "  Jira API token: "
            read -rs INPUT_JIRA_TOKEN  # -s = silent (no echo)
            echo ""
            if [ -n "$INPUT_JIRA_TOKEN" ]; then
                # Append under existing Jira comment if we just wrote it, otherwise add new block
                if ! grep -q '# Claude Code — Jira integration' "$SHELL_PROFILE" 2>/dev/null; then
                    echo "" >> "$SHELL_PROFILE"
                    echo "# Claude Code — Jira integration" >> "$SHELL_PROFILE"
                fi
                echo "export JIRA_API_TOKEN=\"$INPUT_JIRA_TOKEN\"" >> "$SHELL_PROFILE"
                export JIRA_API_TOKEN="$INPUT_JIRA_TOKEN"
                echo "  ✓ JIRA_API_TOKEN saved to $SHELL_PROFILE"
            else
                echo "  ⊘ Skipped JIRA_API_TOKEN"
            fi
        else
            echo "  ✓ JIRA_API_TOKEN already set"
        fi

        # ── Workspace path (for skill path substitution) ──
        DEFAULT_WORKSPACE="$(cd "$SCRIPT_DIR/.." && pwd)"
        HARDCODED_WORKSPACE="/Users/trungthach/IdeaProjects"
        if [ "$DEFAULT_WORKSPACE" != "$HARDCODED_WORKSPACE" ]; then
            echo ""
            echo "  Your workspace: $DEFAULT_WORKSPACE"
            echo "  Skills have hardcoded paths to: $HARDCODED_WORKSPACE"
            printf "  Auto-fix skill paths to your workspace? [Y/n] "
            read -r FIX_PATHS
            FIX_PATHS="${FIX_PATHS:-Y}"
            REWRITE_PATHS="$FIX_PATHS"
        else
            REWRITE_PATHS="n"
        fi

        # ── Verify Jira connection ──
        if [ -n "$JIRA_EMAIL" ] && [ -n "$JIRA_API_TOKEN" ]; then
            echo ""
            printf "  Verifying Jira connection... "
            HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
                -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
                "https://mosoteam.atlassian.net/rest/api/2/myself" 2>/dev/null)
            if [ "$HTTP_CODE" = "200" ]; then
                echo "✓ Connected"
            elif [ "$HTTP_CODE" = "401" ]; then
                echo "✗ Auth failed (check email/token)"
            elif [ "$HTTP_CODE" = "000" ]; then
                echo "✗ No network (will work once online)"
            else
                echo "? HTTP $HTTP_CODE (may still work)"
            fi
        fi
    else
        echo "  Skipped. Set these manually later:"
        echo "    export JIRA_EMAIL=\"your@email.com\""
        echo "    export JIRA_API_TOKEN=\"your-token\""
        REWRITE_PATHS="n"
    fi
else
    echo "  ✓ JIRA_EMAIL and JIRA_API_TOKEN already configured"
    # Still check workspace path
    DEFAULT_WORKSPACE="$(cd "$SCRIPT_DIR/.." && pwd)"
    HARDCODED_WORKSPACE="/Users/trungthach/IdeaProjects"
    REWRITE_PATHS="n"
    if [ "$DEFAULT_WORKSPACE" != "$HARDCODED_WORKSPACE" ]; then
        echo ""
        echo "  Your workspace: $DEFAULT_WORKSPACE"
        echo "  Skills have hardcoded paths to: $HARDCODED_WORKSPACE"
        printf "  Auto-fix skill paths to your workspace? [Y/n] "
        read -r FIX_PATHS
        FIX_PATHS="${FIX_PATHS:-Y}"
        REWRITE_PATHS="$FIX_PATHS"
    fi
fi
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

# --- Path rewriting (if workspace differs) ---
if [[ "$REWRITE_PATHS" =~ ^[Yy]$ ]]; then
    echo "--- Path Rewriting ---"
    HARDCODED_WORKSPACE="/Users/trungthach/IdeaProjects"
    DEFAULT_WORKSPACE="$(cd "$SCRIPT_DIR/.." && pwd)"
    REWRITTEN=0

    # Rewrite skill files
    for f in "$USER_CLAUDE/skills"/*/SKILL.md; do
        [ -f "$f" ] || continue
        if grep -q "$HARDCODED_WORKSPACE" "$f" 2>/dev/null; then
            sed -i '' "s|$HARDCODED_WORKSPACE|$DEFAULT_WORKSPACE|g" "$f"
            echo "  REWRITTEN: $(basename "$(dirname "$f")")/SKILL.md"
            REWRITTEN=$((REWRITTEN + 1))
        fi
    done

    # Rewrite knowledge/memory files
    for f in "$MEMORY_DIR"/*.md; do
        [ -f "$f" ] || continue
        if grep -q "$HARDCODED_WORKSPACE" "$f" 2>/dev/null; then
            sed -i '' "s|$HARDCODED_WORKSPACE|$DEFAULT_WORKSPACE|g" "$f"
            echo "  REWRITTEN: knowledge/$(basename "$f")"
            REWRITTEN=$((REWRITTEN + 1))
        fi
    done

    # Rewrite agent files
    for f in "$USER_CLAUDE/agents"/*.md; do
        [ -f "$f" ] || continue
        if grep -q "$HARDCODED_WORKSPACE" "$f" 2>/dev/null; then
            sed -i '' "s|$HARDCODED_WORKSPACE|$DEFAULT_WORKSPACE|g" "$f"
            echo "  REWRITTEN: agents/$(basename "$f")"
            REWRITTEN=$((REWRITTEN + 1))
        fi
    done

    # Also rewrite the encoded memory path in skills (e.g., ~/.claude/projects/-Users-trungthach-IdeaProjects/)
    OLD_ENCODED=$(echo "$HARDCODED_WORKSPACE" | sed 's|^/|-|; s|/|-|g')
    NEW_ENCODED=$(echo "$DEFAULT_WORKSPACE" | sed 's|^/|-|; s|/|-|g')
    if [ "$OLD_ENCODED" != "$NEW_ENCODED" ]; then
        for f in "$USER_CLAUDE/skills"/*/SKILL.md; do
            [ -f "$f" ] || continue
            if grep -q "$OLD_ENCODED" "$f" 2>/dev/null; then
                sed -i '' "s|$OLD_ENCODED|$NEW_ENCODED|g" "$f"
            fi
        done
    fi

    echo "✓ Paths: $REWRITTEN files rewritten ($HARDCODED_WORKSPACE → $DEFAULT_WORKSPACE)"
    echo ""
fi

# --- Summary ---
echo "=== Done! ==="
echo ""
echo "Agents:    $(ls "$USER_CLAUDE/agents"/*.md 2>/dev/null | wc -l | tr -d ' ') files"
echo "Skills:    $(ls -d "$USER_CLAUDE/skills"/*/ 2>/dev/null | wc -l | tr -d ' ') directories"
echo "Knowledge: $(ls "$MEMORY_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ') files"
echo ""
echo "Your existing agents/skills were preserved. Only new or updated files were added."

# Show status of env vars
echo ""
echo "--- Environment Status ---"
if [ -n "$JIRA_EMAIL" ]; then
    echo "  ✓ JIRA_EMAIL = $JIRA_EMAIL"
else
    echo "  ✗ JIRA_EMAIL not set (needed for /fix-parser, /new-parser, /tera)"
fi
if [ -n "$JIRA_API_TOKEN" ]; then
    echo "  ✓ JIRA_API_TOKEN = ****$(echo "$JIRA_API_TOKEN" | tail -c 5)"
else
    echo "  ✗ JIRA_API_TOKEN not set (get one at https://id.atlassian.com/manage-profile/security/api-tokens)"
fi
echo ""

# Check for GCS auth
if command -v gcloud &>/dev/null; then
    GCLOUD_ACCOUNT=$(gcloud config get-value account 2>/dev/null)
    if [ -n "$GCLOUD_ACCOUNT" ] && [ "$GCLOUD_ACCOUNT" != "(unset)" ]; then
        echo "  ✓ gcloud authenticated as $GCLOUD_ACCOUNT"
    else
        echo "  ⚠ gcloud installed but not logged in — run: gcloud auth login"
    fi
else
    echo "  ⚠ gcloud not installed — needed for ratesheet downloads"
    echo "    Install: https://cloud.google.com/sdk/docs/install"
fi
echo ""
echo "Restart Claude Code to pick up changes."

---
name: sync
description: Pull latest, sync agents, skills, and knowledge (cookbook, pricing, feedback memories) into the repo. Add-only, no deletes. Commit and push.
allowed-tools: Bash, Read, Glob, Grep
---

# Sync Agents, Skills & Knowledge

Synchronize agents, skills, and knowledge files between `~/.claude/` and the tools repo. **Add-only** — never delete files from the repo.

## Constants

```
REPO_CLAUDE="/Users/trungthach/IdeaProjects/tools/.claude"
MEMORY_DIR="$HOME/.claude/projects/-Users-trungthach-IdeaProjects/memory"
```

## Steps

Run these steps in order:

### Step 1: Pull latest
```bash
cd /Users/trungthach/IdeaProjects/tools
git stash 2>/dev/null; git pull --rebase; git stash pop 2>/dev/null
```

### Step 2: Sync agents
Compare `~/.claude/agents/` with `$REPO_CLAUDE/agents/`. For each `.md` file:
- NOT in repo → copy (NEW)
- Differs → copy (UPDATED)
- Matches → skip (UNCHANGED)

**Never delete** files from the repo.

```bash
REPO_CLAUDE="/Users/trungthach/IdeaProjects/tools/.claude"
cd ~/.claude/agents
for f in *.md; do
  if [ ! -f "$REPO_CLAUDE/agents/$f" ]; then
    cp "$f" "$REPO_CLAUDE/agents/$f"
    echo "NEW: agents/$f"
  elif ! diff -q "$f" "$REPO_CLAUDE/agents/$f" > /dev/null 2>&1; then
    cp "$f" "$REPO_CLAUDE/agents/$f"
    echo "UPDATED: agents/$f"
  else
    echo "UNCHANGED: agents/$f"
  fi
done
```

### Step 3: Sync skills
Compare `~/.claude/skills/` with `$REPO_CLAUDE/skills/`. For each skill directory:
- NOT in repo → copy (NEW)
- SKILL.md differs → copy (UPDATED)
- Matches → skip (UNCHANGED)

**Never delete** skill directories from the repo.

```bash
cd ~/.claude/skills
for d in */; do
  skill="${d%/}"
  if [ ! -d "$REPO_CLAUDE/skills/$skill" ]; then
    cp -r "$skill" "$REPO_CLAUDE/skills/$skill"
    echo "NEW: skills/$skill"
  elif [ -f "$skill/SKILL.md" ] && [ -f "$REPO_CLAUDE/skills/$skill/SKILL.md" ]; then
    if ! diff -q "$skill/SKILL.md" "$REPO_CLAUDE/skills/$skill/SKILL.md" > /dev/null 2>&1; then
      cp -r "$skill"/* "$REPO_CLAUDE/skills/$skill/"
      echo "UPDATED: skills/$skill"
    else
      echo "UNCHANGED: skills/$skill"
    fi
  else
    echo "UNCHANGED: skills/$skill"
  fi
done
```

### Step 4: Sync knowledge (cookbooks, pricing, feedback)

Sync important memory files from project memory into `$REPO_CLAUDE/knowledge/`.

**Knowledge files to sync** (add-only, never delete):

| Source (project memory) | Purpose |
|------------------------|---------|
| `parser_fix_cookbook.md` | Fix-parser tier history, cached paths, fix patterns |
| `parser_build_cookbook.md` | New-parser build history, table patterns, similar lenders |
| `parser_pricing_knowledge.md` | Pricing domain knowledge, common mistakes |
| `feedback_*.md` | User preferences (commit style, review rules, etc.) |
| `ai_parser_workflow.md` | Parser workflow knowledge |
| `project_architecture.md` | Architecture understanding |

```bash
REPO_CLAUDE="/Users/trungthach/IdeaProjects/tools/.claude"
MEMORY_DIR="$HOME/.claude/projects/-Users-trungthach-IdeaProjects/memory"
mkdir -p "$REPO_CLAUDE/knowledge"

# Sync specific knowledge files
for f in parser_fix_cookbook.md parser_build_cookbook.md parser_pricing_knowledge.md ai_parser_workflow.md project_architecture.md; do
  if [ -f "$MEMORY_DIR/$f" ]; then
    if [ ! -f "$REPO_CLAUDE/knowledge/$f" ]; then
      cp "$MEMORY_DIR/$f" "$REPO_CLAUDE/knowledge/$f"
      echo "NEW: knowledge/$f"
    elif ! diff -q "$MEMORY_DIR/$f" "$REPO_CLAUDE/knowledge/$f" > /dev/null 2>&1; then
      cp "$MEMORY_DIR/$f" "$REPO_CLAUDE/knowledge/$f"
      echo "UPDATED: knowledge/$f"
    else
      echo "UNCHANGED: knowledge/$f"
    fi
  fi
done

# Sync all feedback_*.md files
for f in "$MEMORY_DIR"/feedback_*.md; do
  if [ -f "$f" ]; then
    fname=$(basename "$f")
    if [ ! -f "$REPO_CLAUDE/knowledge/$fname" ]; then
      cp "$f" "$REPO_CLAUDE/knowledge/$fname"
      echo "NEW: knowledge/$fname"
    elif ! diff -q "$f" "$REPO_CLAUDE/knowledge/$fname" > /dev/null 2>&1; then
      cp "$f" "$REPO_CLAUDE/knowledge/$fname"
      echo "UPDATED: knowledge/$fname"
    else
      echo "UNCHANGED: knowledge/$fname"
    fi
  fi
done
```

### Step 5: Check for changes
```bash
cd /Users/trungthach/IdeaProjects/tools
git status --short .claude/
```

If no changes, report "Everything is up to date" and stop.

### Step 6: Commit and push
Stage `.claude/agents/`, `.claude/skills/`, and `.claude/knowledge/`, commit and push.

```bash
git add .claude/agents/ .claude/skills/ .claude/knowledge/
git commit -m "Sync: <summary of NEW/UPDATED items>"
git push
```

### Step 7: Report
Show the user a summary table:

| File | Status |
|------|--------|
| agents/xyz.md | NEW / UPDATED / UNCHANGED |
| skills/xyz | NEW / UPDATED / UNCHANGED |
| knowledge/xyz.md | NEW / UPDATED / UNCHANGED |

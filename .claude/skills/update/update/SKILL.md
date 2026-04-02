---
name: update
description: Pull latest agents, skills, and knowledge from the sync repo into local ~/.claude. Read-only — never pushes changes back.
allowed-tools: Bash, Read, Glob, Grep
---

# /update — Pull & Update Agents, Skills & Knowledge

Pull the latest from the sync repo and merge into local `~/.claude/`. **Never pushes** — local-only changes stay local.

## Constants

```
REPO="/Users/trungthach/IdeaProjects/tools"
REPO_CLAUDE="$REPO/.claude"
MEMORY_DIR="$HOME/.claude/projects/-Users-trungthach-IdeaProjects/memory"
```

## Steps

Run these steps in order:

### Step 1: Pull latest from repo
```bash
cd /Users/trungthach/IdeaProjects/tools
git stash 2>/dev/null; git pull --rebase; git stash pop 2>/dev/null
```

### Step 2: Update agents
For each `.md` file in `$REPO_CLAUDE/agents/`:
- NOT in local → copy (NEW)
- Differs from local → copy (UPDATED)
- Matches → skip (UNCHANGED)

**Never delete** local agents that aren't in the repo.

```bash
REPO_CLAUDE="/Users/trungthach/IdeaProjects/tools/.claude"
mkdir -p ~/.claude/agents
for f in "$REPO_CLAUDE/agents"/*.md; do
  [ -f "$f" ] || continue
  fname=$(basename "$f")
  if [ ! -f "$HOME/.claude/agents/$fname" ]; then
    cp "$f" "$HOME/.claude/agents/$fname"
    echo "NEW: agents/$fname"
  elif ! diff -q "$f" "$HOME/.claude/agents/$fname" > /dev/null 2>&1; then
    cp "$f" "$HOME/.claude/agents/$fname"
    echo "UPDATED: agents/$fname"
  else
    echo "UNCHANGED: agents/$fname"
  fi
done
```

### Step 3: Update skills
For each skill directory in `$REPO_CLAUDE/skills/`:
- NOT in local → copy (NEW)
- SKILL.md differs → copy all files in that skill (UPDATED)
- Matches → skip (UNCHANGED)

**Never delete** local skills that aren't in the repo.

```bash
REPO_CLAUDE="/Users/trungthach/IdeaProjects/tools/.claude"
mkdir -p ~/.claude/skills
for d in "$REPO_CLAUDE/skills"/*/; do
  [ -d "$d" ] || continue
  skill=$(basename "$d")
  if [ ! -d "$HOME/.claude/skills/$skill" ]; then
    cp -r "$d" "$HOME/.claude/skills/$skill"
    echo "NEW: skills/$skill"
  elif [ -f "$d/SKILL.md" ] && [ -f "$HOME/.claude/skills/$skill/SKILL.md" ]; then
    if ! diff -q "$d/SKILL.md" "$HOME/.claude/skills/$skill/SKILL.md" > /dev/null 2>&1; then
      cp -r "$d"/* "$HOME/.claude/skills/$skill/"
      echo "UPDATED: skills/$skill"
    else
      echo "UNCHANGED: skills/$skill"
    fi
  else
    echo "UNCHANGED: skills/$skill"
  fi
done
```

### Step 4: Update knowledge
Merge knowledge files from `$REPO_CLAUDE/knowledge/` into project memory. Only add new or update files where repo has newer content.

**Never delete** local memory files that aren't in the repo.

```bash
REPO_CLAUDE="/Users/trungthach/IdeaProjects/tools/.claude"
MEMORY_DIR="$HOME/.claude/projects/-Users-trungthach-IdeaProjects/memory"
mkdir -p "$MEMORY_DIR"
for f in "$REPO_CLAUDE/knowledge"/*.md; do
  [ -f "$f" ] || continue
  fname=$(basename "$f")
  if [ ! -f "$MEMORY_DIR/$fname" ]; then
    cp "$f" "$MEMORY_DIR/$fname"
    echo "NEW: knowledge/$fname"
  elif ! diff -q "$f" "$MEMORY_DIR/$fname" > /dev/null 2>&1; then
    REPO_SIZE=$(wc -c < "$f")
    LOCAL_SIZE=$(wc -c < "$MEMORY_DIR/$fname")
    if [ "$REPO_SIZE" -gt "$LOCAL_SIZE" ]; then
      cp "$f" "$MEMORY_DIR/$fname"
      echo "UPDATED: knowledge/$fname (repo has newer content)"
    else
      echo "UNCHANGED: knowledge/$fname (local is newer)"
    fi
  else
    echo "UNCHANGED: knowledge/$fname"
  fi
done
```

### Step 5: Report
Show the user a summary table:

| File | Status |
|------|--------|
| agents/xyz.md | NEW / UPDATED / UNCHANGED |
| skills/xyz | NEW / UPDATED / UNCHANGED |
| knowledge/xyz.md | NEW / UPDATED / UNCHANGED |

End with: "Local updated. No changes were pushed to the repo."

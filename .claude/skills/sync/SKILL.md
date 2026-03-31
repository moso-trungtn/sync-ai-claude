---
name: sync
description: Pull latest repo, sync new/updated agents and skills from ~/.claude/ into the repo (add-only, no deletes), commit and push.
allowed-tools: Bash, Read, Glob, Grep
---

# Sync Agents & Skills

Synchronize agents and skills between `~/.claude/` and the tools repo. **Add-only** — never delete files from the repo.

## Steps

Run these steps in order:

### Step 1: Pull latest
```bash
cd /Users/trungthach/IdeaProjects/tools
git pull --rebase
```

### Step 2: Resolve repo path
```bash
REPO_CLAUDE="/Users/trungthach/IdeaProjects/tools/.claude"
```

### Step 3: Sync agents
Compare `~/.claude/agents/` with `$REPO_CLAUDE/agents/`. For each `.md` file in `~/.claude/agents/`:
- If it does NOT exist in the repo → copy it in (NEW)
- If it exists but content differs → copy the updated version (UPDATED)
- If it exists and content matches → skip (UNCHANGED)

**Never delete** files from `$REPO_CLAUDE/agents/` that don't exist in `~/.claude/agents/`.

```bash
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

### Step 4: Sync skills
Compare `~/.claude/skills/` with `$REPO_CLAUDE/skills/`. For each skill directory:
- If it does NOT exist in the repo → copy it in (NEW)
- If it exists but SKILL.md differs → copy the updated version (UPDATED)
- If it exists and matches → skip (UNCHANGED)

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

### Step 5: Check for changes
```bash
cd /Users/trungthach/IdeaProjects/tools
git status --short .claude/
```

If no changes, report "Everything is up to date" and stop.

### Step 6: Commit and push
Stage only `.claude/agents/` and `.claude/skills/`, commit with a summary of what was added/updated, and push.

```bash
git add .claude/agents/ .claude/skills/
git commit -m "Sync agents and skills: <summary of NEW/UPDATED items>"
git push
```

### Step 7: Report
Show the user a summary table:

| File | Status |
|------|--------|
| agents/xyz.md | NEW / UPDATED / UNCHANGED |
| skills/xyz | NEW / UPDATED / UNCHANGED |

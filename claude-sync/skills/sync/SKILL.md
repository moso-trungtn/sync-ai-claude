---
name: sync
description: Pull latest, sync agents, skills, and all memory files (knowledge) into the repo. Add-only, no deletes. Commit and push.
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
  # synced/ is Claude's own marketplace skill cache, not ours — never sync it
  [ "$skill" = "synced" ] && continue
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

### Step 4: Sync knowledge (all memory files)

Sync **every** `.md` file in the project memory dir into `$REPO_CLAUDE/knowledge/`.

`MEMORY.md` is the master index and is loaded into context on every session — if it ships
without the files it links to, the other machine sees an index of memories that do not exist.
So the rule is: whatever `MEMORY.md` can link to, gets pushed. No allow-list of prefixes.

```bash
REPO_CLAUDE="/Users/trungthach/IdeaProjects/tools/.claude"
MEMORY_DIR="$HOME/.claude/projects/-Users-trungthach-IdeaProjects/memory"
mkdir -p "$REPO_CLAUDE/knowledge"

for f in "$MEMORY_DIR"/*.md; do
  [ -f "$f" ] || continue
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
done
```

**Add-only** — never delete from `$REPO_CLAUDE/knowledge/`.

Then verify the index has no dangling links before committing:

```bash
grep -oE '\]\(([^)]+\.md)\)' "$REPO_CLAUDE/knowledge/MEMORY.md" | sed 's/.*(\(.*\))/\1/' | while read -r link; do
  [ -f "$REPO_CLAUDE/knowledge/$(basename "$link")" ] || echo "MISSING: $link"
done
```

If anything prints `MISSING:`, report it — the index links a memory that does not exist on this
machine either, so it should be removed from `MEMORY.md` rather than shipped broken.

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

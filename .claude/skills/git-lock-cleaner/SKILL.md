---
name: git-lock-cleaner
description: >
  Remove stale Git lock files across all repositories. Use when Git operations fail with
  "index.lock file exists" errors. Triggers: "remove git lock", "clear git locks",
  "fix git lock", "git lock error", "clean git locks", "unlock git".
---

# Git Lock Cleaner Skill

Automatically finds and removes stale `.git/index.lock` files across all Git repositories in the workspace.

## When to Use

Use this skill when encountering errors like:
- "Unable to create '.git/index.lock': File exists"
- "Another git process seems to be running"
- Git operations hang or fail due to stale locks

## How It Works

The skill performs these steps:

### 1. Check for Active Git Processes
First, verify no Git processes are actually running:
```bash
ps aux | grep git | grep -v grep
```

If active Git processes are found, STOP and report them to the user. Do NOT remove locks while Git is running.

### 2. Find All Git Repositories
Locate all `.git` directories in the workspace:
```bash
cd /Users/trungthach/IdeaProjects
find . -type d -name ".git" -not -path "*/target/*" -not -path "*/node_modules/*" 2>/dev/null
```

### 3. Check for Lock Files
For each repository found, check if `.git/index.lock` exists:
```bash
for repo in $(find . -type d -name ".git" -not -path "*/target/*" -not -path "*/node_modules/*" 2>/dev/null); do
    lock_file="${repo}/index.lock"
    if [ -f "$lock_file" ]; then
        echo "FOUND: $lock_file"
    fi
done
```

### 4. Remove Lock Files
Remove each found lock file:
```bash
rm -f /path/to/repo/.git/index.lock
```

### 5. Report Results
Provide a summary:
- Number of repositories scanned
- Lock files found and removed
- Current status of each repository

## Example Output

```
✓ Scanned 3 repositories
✓ Found 1 stale lock file:
  - moso-docs/.git/index.lock (removed)

All repositories are now unlocked and ready for Git operations.
```

## Safety Checks

- NEVER remove lock files if active Git processes are running
- Only target `.git/index.lock` files (not other lock files)
- Exclude build directories (target/, node_modules/, etc.)
- Report what was done so the user can verify

## Common Lock Files

This skill handles:
- `.git/index.lock` — Main index lock (most common)
- Can be extended to handle other Git locks if needed:
  - `.git/refs/heads/*.lock`
  - `.git/HEAD.lock`
  - `.git/config.lock`

## After Running

After cleaning locks, suggest the user retry their Git operation:
```bash
git status  # Verify Git is working
```

## Related Issues

Lock files are typically left behind by:
- Interrupted Git commands (Ctrl+C during commit/add)
- System crashes during Git operations
- Git processes killed abnormally
- File system issues or permissions problems

---
name: check-rate-commit-style
description: "Commit-message conventions for the check-rate repo — bracketed type prefix, imperative subject, no AI-branding trailers"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 87eb54c6-c3e1-4f10-9a2b-bacb0a8ff533
---

For commits in **`/Users/trungthach/IdeaProjects/check-rate`**, use this format:

```
[type] short imperative subject (≤72 chars)

Optional body explaining WHY, wrapped at ~72 chars.
```

**Why:** User asked for the standard "bracketed type" convention that's
common across normal team repos, and explicitly does NOT want commits
branded as AI-generated (no `Co-Authored-By: Claude`, no `🤖 Generated
with Claude Code` trailers). They want the repo to look like any other
human-authored project.

**How to apply:**

- Always start the subject with one bracketed type:
  `[feat]` `[fix]` `[refactor]` `[perf]` `[test]` `[docs]` `[style]`
  `[chore]` `[revert]`.
- Subject in imperative mood, lowercase after the bracket, no trailing
  period, ≤72 chars total.
- **Never** add `Co-Authored-By:` trailers or AI-branding footers.
- Body (optional) is wrapped at ~72 chars and explains the *why*. The
  diff already shows the *what*.
- If a commit honestly does two unrelated things, split it.
- The repo's `CLAUDE.md` has the full convention with good/bad examples.

Same convention applies to other repos only if explicitly stated;
this is currently a check-rate-specific rule.

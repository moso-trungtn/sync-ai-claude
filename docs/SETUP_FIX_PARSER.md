# Setting Up `/fix-parser` on a New Device

This guide walks you through everything needed to run the `/fix-parser` skill on a freshly cloned machine.

---

## Prerequisites

| Requirement | Version | Check |
|-------------|---------|-------|
| **Claude Code CLI** | Latest | `claude --version` |
| **Java (JDK)** | 11+ | `java -version` |
| **Maven** | 3.6+ | `mvn -version` |
| **Git** | Any | `git --version` |
| **Google Cloud SDK** | Latest | `gcloud --version` |
| **Python 3** | 3.8+ (for dashboard) | `python3 --version` |

---

## Step 1: Clone the Required Repositories

The fix-parser pipeline operates across **three** repos. They must all live under the same parent directory:

```bash
mkdir -p ~/IdeaProjects && cd ~/IdeaProjects

# 1. This tools repo (agents, skills, knowledge, dashboard)
git clone <tools-repo-url> tools

# 2. The pricing module (parser source code — Tables, RateParser, AdjParser)
git clone <moso-pricing-repo-url> moso-pricing

# 3. The test harness (test infrastructure, ratesheets, expectations)
git clone <packs-repo-url> packs
```

Your directory structure should look like:

```
~/IdeaProjects/
├── tools/              ← agents, skills, dashboard
├── moso-pricing/       ← parser Java source code
└── packs/
    └── loan/           ← test harness, ratesheets, shell scripts
```

---

## Step 2: Generate a Jira API Token (before running setup)

You'll need this during setup. Get it now:

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create API token**
3. Give it a name like "Claude Code"
4. Copy the token — you'll paste it in the next step

---

## Step 3: Run the Setup Script

The setup script does everything in one interactive session:

```bash
cd ~/IdeaProjects/tools
bash setup.sh
```

**It will:**
1. **Ask for your Jira email** and **API token** — saves them to your shell profile (`~/.zshrc` or `~/.bashrc`)
2. **Verify the Jira connection** — confirms your credentials work
3. **Detect workspace path** — if your repos aren't at `/Users/trungthach/IdeaProjects`, it auto-rewrites all hardcoded paths in skill files
4. **Copy agents** to `~/.claude/agents/` (ba, dev, parser-dev, code-reviewer, etc.)
5. **Copy skills** to `~/.claude/skills/` (fix-parser, new-parser, etc.)
6. **Copy knowledge** to `~/.claude/projects/<encoded-path>/memory/` (cookbook, architecture docs, feedback memories)
7. **Check gcloud status** — warns if not installed or not logged in
8. **Show environment summary** — green checks for everything configured, warnings for anything missing

**Example output:**
```
=== Setting up Claude Code agents, skills & knowledge ===

--- Environment ---
  Jira email (e.g., name@loanfactory.com): john@loanfactory.com
  ✓ JIRA_EMAIL saved to /Users/john/.zshrc
  Get your API token from: https://id.atlassian.com/manage-profile/security/api-tokens
  Jira API token: 
  ✓ JIRA_API_TOKEN saved to /Users/john/.zshrc
  Verifying Jira connection... ✓ Connected

--- Agents ---
  NEW: agents/parser-dev.md
  ...
✓ Agents: 8 new, 0 updated, 0 unchanged

--- Skills ---
  NEW: skills/fix-parser
  ...
✓ Skills: 5 new, 0 updated, 0 unchanged

--- Knowledge ---
  NEW: knowledge/parser_fix_cookbook.md
  ...
✓ Knowledge: 10 new, 0 updated, 0 unchanged

--- Environment Status ---
  ✓ JIRA_EMAIL = john@loanfactory.com
  ✓ JIRA_API_TOKEN = ****xyz1
  ✓ gcloud authenticated as john@loanfactory.com

Restart Claude Code to pick up changes.
```

> **Re-running is safe.** The script never overwrites or deletes existing files — it only adds new ones or updates changed ones. Environment variables already in your shell profile are skipped.

---

## Step 4: Configure Atlassian MCP Server

The `/fix-parser` skill uses Atlassian MCP tools for Jira transitions (moving tickets to "In Progress", etc.).

**If using Claude Code with built-in Atlassian** (via `claude.ai`): it works automatically.

**Otherwise**, add it manually:

```bash
claude mcp add atlassian -- npx @anthropic/atlassian-mcp-server
```

Verify by asking Claude: "Search Jira for parser failed tasks."

---

## Step 5: Configure GCS Access (for Ratesheet Downloads)

```bash
# Login to Google Cloud
gcloud auth login

# Set the project (ask your team for the project ID)
gcloud config set project <your-gcs-project-id>

# Verify access
gcloud storage ls gs://<your-bucket>/
```

> The setup script checks gcloud status and warns you if this isn't done yet.

---

## Step 6: Build moso-pricing JAR

```bash
cd ~/IdeaProjects/moso-pricing
mvn install -DskipTests -Pjar-packaging -Dgwt.compiler.skip=true
```

The pipeline rebuilds this automatically, but doing it once upfront catches build issues early.

---

## Step 7: Verify the Test Harness

```bash
cd ~/IdeaProjects/packs/loan
mvn test -Dtest=AdjustmentParsersTest#testParamount 2>&1 | tail -5
```

You should see `BUILD SUCCESS` (or a test failure with a proper report — not a compilation error).

---

## Step 8: (Optional) Start the Agent Dashboard

The dashboard shows real-time pipeline progress in a web UI:

```bash
cd ~/IdeaProjects/tools
python3 agent-dashboard/server.py &
```

Open http://localhost:3847 to see live agent status.

---

## Step 9: Restart Claude Code and Run

```bash
# Restart Claude Code to pick up new skills, then:
/fix-parser
```

Or with a specific assignee:

```
/fix-parser @712020:abc123-your-atlassian-account-id
```

The pipeline will:
1. Load cookbook & memories
2. Query Jira for `[Parser failed]` tasks assigned to you
3. Show a table with predicted fix tiers
4. Ask which tasks to fix
5. Download ratesheets, classify errors, fix (auto or agent), verify, commit

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `JIRA_EMAIL=MISSING` | Run `bash setup.sh` again — it will prompt for missing vars |
| `Atlassian MCP not available` | Configure MCP server (Step 4) |
| `gcloud: command not found` | Install Google Cloud SDK (`brew install google-cloud-sdk`) |
| `mvn: command not found` | Install Maven (`brew install maven`) |
| `BUILD FAILURE` on moso-pricing | Check Java version (`java -version`), needs JDK 11+ |
| Skill not found when typing `/fix-parser` | Run `setup.sh` again and restart Claude Code |
| `No expectations file for <lender>` | Normal on first run — pipeline handles this with `-Daccept` |
| Dashboard not loading | Check `python3 agent-dashboard/server.py` is running |

---

## Summary Checklist

- [ ] Clone all 3 repos (`tools`, `moso-pricing`, `packs`) under same parent
- [ ] Get Jira API token from https://id.atlassian.com/manage-profile/security/api-tokens
- [ ] Run `bash setup.sh` from `tools/` (configures env vars, copies skills, fixes paths)
- [ ] Atlassian MCP server configured in Claude Code
- [ ] `gcloud auth login` completed
- [ ] `mvn install` on moso-pricing succeeds
- [ ] Test harness runs (`packs/loan` mvn test)
- [ ] Restart Claude Code

---
name: AI Parser Workflow (packs/loan)
description: Complete parser-fix workflow, tool registry, and testing architecture for mortgage ratesheet parsing
type: project
---

# AI Parser Workflow for Ratesheet Testing

## Quick Activation

When user says **"ai-parser"**, activate parser-fix mode and:
1. Read lender registry from `moso-pricing/docs/MEMORY.md`
2. Present tool capabilities
3. Ask which lender + which task
4. Operate in parser context using tools below

## 5 Main Tools (run from `packs/loan/`)

### 1. `lender-info.sh` — Zero-token lender lookup
```bash
./lender-info.sh Freedom              # Full lender info
./lender-info.sh ElevenMortgage       # Case-insensitive, CamelCase works
./lender-info.sh --list               # List all known lenders
```
Resolves: test methods, parser classes, Tables class, constants, dump dirs, doc files (via grep, zero tokens)

### 2. `parser-fix.sh` — Test + error report pipeline
```bash
./parser-fix.sh Freedom --ratesheet /path/to/new.xlsx --both    # Both adj + rate
./parser-fix.sh Freedom --adj                                    # Adj only
./parser-fix.sh Freedom --rate                                   # Rate only
./parser-fix.sh Freedom                                          # Both, classpath ratesheet
```
Output: `/tmp/parser-fix/<lender>/report.txt` (~50 lines, read this not Maven logs)

Flags: `--ratesheet <path>` | `--adj` | `--rate` | `--both` | `--dump` | `--accept`

### 3. `download-ratesheet.sh` — Download from GCS + register
```bash
./download-ratesheet.sh Paramount                    # Standard
./download-ratesheet.sh Freedom --zone 1             # Specific zone
./download-ratesheet.sh Freedom --all                # All zones + adj
./download-ratesheet.sh ElevenMortgage --nonqm       # NonQM variant
./download-ratesheet.sh Paramount --dry-run          # Preview only
```
Automatically: downloads, names (`<snake_case>_<YYYYMMDD>.<ext>`), updates RatesheetFiles.java, git-adds

Flags: `--zone N` | `--zones SPEC` | `--adj` | `--nonqm` | `--all` | `--ext EXT` | `--dry-run` | `--no-git` | `--no-java` | `--date YYYYMMDD`

### 4. `ratesheet-update.sh` — Full cycle (dump + diff + test)
```bash
./ratesheet-update.sh /path/to/new.xlsx testLenderName          # Full cycle
./ratesheet-update.sh /path/to/new.xlsx testLenderName --dump-only
./ratesheet-update.sh /path/to/new.xlsx testLenderName --adj-only --skip-dump
```
Output: `/tmp/ratesheet-update/<basename>/` (includes summary report)

### 5. `cleanup-ratesheets.sh` — Remove unused ratesheets
```bash
./cleanup-ratesheets.sh              # Dry run
./cleanup-ratesheets.sh --apply      # Actually remove files
```

## Advanced: `ratesheet.sh` — Unified Lifecycle
```bash
./ratesheet.sh build                              # Install moso-pricing JAR to M2
./ratesheet.sh status [Lender]                    # Quick health check
./ratesheet.sh check Paramount                    # Download + build + test (one command)
./ratesheet.sh check Paramount --skip-download    # Build + test only
./ratesheet.sh diff Paramount                     # Dump old+new, compare
./ratesheet.sh land Paramount                     # Replace constants, verify, cleanup
./ratesheet.sh land Paramount --dry-run           # Preview what land would do
```

## AI Parser Rules (CRITICAL)

1. **Always git-add downloaded ratesheets** — never use `--no-git` unless user explicitly asks
2. **Always ask about downloading first** — when user says "check" or "fix", ask if they want to download latest
3. **Always test with new ratesheet** — pass `--ratesheet <path>` to parser-fix.sh after download
4. **Always rebuild moso-pricing before tests** — run `mvn install -DskipTests -Pjar-packaging -Dgwt.compiler.skip=true` in moso-pricing first
5. **Check ≠ Fix** — "check" means: download, rebuild, test, summarize (no changes). "fix" means: code changes allowed
6. **Always update CLAUDE.md** — when learning new workflow rules, update the repo file

## Common Workflows

### Typical parser fix
```
lender-info.sh → read lender doc → parser-fix.sh → read report
→ fix code → mvn install moso-pricing → parser-fix.sh (re-test)
→ replace ratesheet + run -Daccept → commit
```

### New ratesheet arrived (quick)
```
ratesheet.sh check <Lender>         # download + build + test (one command)
→ fix code if needed → ratesheet.sh check <Lender> --skip-download
→ ratesheet.sh land <Lender>        # replace constants + verify + cleanup
```

### New ratesheet arrived (detailed)
```
download-ratesheet.sh → parser-fix.sh → read report → fix code
→ mvn install moso-pricing → parser-fix.sh (re-test)
→ update RatesheetFiles + run -Daccept → commit
```

### Just exploring a lender
```
lender-info.sh → read doc
ratesheet.sh status <Lender>    # quick health check
```

## Testing Architecture (AdjustmentParsersTest)

Uses **file-based snapshot expectations** (not inline assertions):

1. **Auto-registration**: All calculator tables auto-discovered via `HasTableInfos.calculators()`
2. **Expectations files**: `src/test/resources/adj-expectations/<lenderKey>.txt` (key=value format)
3. **State fields**: `adjA.assertField(LenderAdjustments.states_field_N)`
4. **Diff on failure**: Shows `fieldName (tableName)`

### Accept workflow
- **First run**: Fails with "No expectations file...". Run with `-Daccept` to create
- **`-Daccept`**: Saves silently, no exception
- **`adjA.acceptChanges()`**: Saves, throws exception (IDE workflow — remove before commit)
- **Subsequent runs**: Compares with expectations, shows diff on mismatch

### Maven commands
```bash
mvn test -Dtest=AdjustmentParsersTest#testParamount                    # Normal
mvn test -Dtest=AdjustmentParsersTest#testParamount -Daccept          # Accept
mvn test -Dtest=AdjustmentParsersTest#testParamount -Dratesheet.path=/path/to/new.xlsx -Daccept
```

## NewAdjustmentDetector

Detects new adjustment tables in ratesheets. Expected files: `src/test/resources/expected-new-adj/<ParserClassName>.txt`

```bash
mvn test -Dtest=AdjustmentParsersTest#testQuickenLoans -Daccept.new.adj
mvn test -Dtest=AdjustmentParsersTest#testQuickenLoans -Dratesheet.path=/path/to/new.pdf -Daccept -Daccept.new.adj
```

Enabled for 57 lenders (all passing adj parsers using PageParser)

## Build Workflow: Critical!

`packs/loan` depends on `moso-pricing` JAR from local Maven M2.

**MUST install moso-pricing before running packs/loan tests:**

```bash
cd /path/to/moso-pricing
mvn install -DskipTests -Pjar-packaging -Dgwt.compiler.skip=true

cd /path/to/packs/loan
./parser-fix.sh <LenderName> --ratesheet /path/to/file --both
```

**Why `-Pjar-packaging`?**
- `war-packaging` (default) → produces WAR, useless for dependency
- `jar-packaging` → produces JAR, required by packs/loan

**When to reinstall:**
- After changes to `*Tables.java`, `*Parser.java`, or any moso-pricing/src/main/ class
- NOT needed for packs/loan/src/test/ changes (test code is local)

## Maven Gotchas

- **Run from `packs/loan/` directly** (NOT `packs/` with `-pl loan`)
- `RatesheetDumpTest` is @Disabled — need `-Djunit.jupiter.conditions.deactivate=*`
- "Please remember to upload..." = transient, just re-run
- "No expectations file..." = run with `-Daccept` to create
- "Table changes..." = review diff, run with `-Daccept` to accept
- "N new, M removed" = review diff labels, run with `-Daccept.new.adj`

## Cross-References

| Resource | Location |
|----------|----------|
| Detailed parser-fix workflow | `moso-pricing/CLAUDE.md` |
| Lender registry + arch docs | `moso-pricing/docs/MEMORY.md` |
| Per-lender deep docs | `moso-pricing/docs/lenders/<lender>.md` |
| Common fix patterns | `moso-pricing/docs/parser-patterns.md` |
| Ratesheet registry | `packs/loan/src/test/java/com/mvu/loan/RatesheetFiles.java` |
| Adj expectations | `packs/loan/src/test/resources/adj-expectations/<lenderKey>.txt` |
| New adj expectations | `packs/loan/src/test/resources/expected-new-adj/<ParserClassName>.txt` |

## Key Example Interactions

```
User: ai-parser
AI:   [reads lender registry] I can help with ratesheet parser tasks:
      • Download — fetch latest ratesheet from GCS
      • Fix — run tests, get error report, fix parser code
      • Test — run adj/rate tests against a ratesheet
      • Dump — export ratesheet to CSV/PNG for inspection
      • Info — look up lender metadata (classes, paths, docs)
      Which lender and task?

User: fix Freedom with /Downloads/freedom_zone1_0304.xlsx
AI:   [runs lender-info.sh Freedom, reads docs/lenders/freedom.md,
       runs parser-fix.sh Freedom --ratesheet ... --both,
       reads report.txt, fixes code]

User: download Paramount
AI:   [runs download-ratesheet.sh Paramount --dry-run first,
       then downloads, shows constants added]
```

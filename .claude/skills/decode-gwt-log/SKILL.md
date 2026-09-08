---
name: decode-gwt-log
description: >
  Decode obfuscated GWT production stack traces into readable Java class/method names.
  Use when given a production log containing "Unknown.XYZ(Unknown Source:N)" frames.
  Triggers: "decode log", "decode stack trace", "parse log", "read production log",
  "gwt log", "obfuscated stack trace".
---

# Decode GWT Log Skill

You are decoding a GWT-compiled production stack trace for the moso mortgage platform.

GWT compiles Java → JavaScript and obfuscates all class/method names in production.
Symbol maps stored in GCS map obfuscated names back to Java source locations.

## GCS Symbol Map Location

```
gs://lender-rate/c/WEB-INF/deploy/moso/symbolMaps/<HASH>.symbolMap
```

The `<HASH>` matches the `.cache.js` permutation hash embedded in the log.

## Process

### Step 1: Extract the permutation hash

Look for it in one of these locations in the raw log:
- In the `changes` array: a 32-char hex string like `7E23CDB6BEBD5B5C2A2EEA8F2BF28BB8`
- As a URL path: `.../moso/<HASH>.cache.js`
- Directly stated by the user

If there are multiple hashes, pick the one that matches a `.cache.js` file (not `.cache.txt`).

### Step 2: Download the symbol map (cache locally, auto-clear old files)

```bash
HASH=<extracted hash>
CACHE_DIR="/tmp/gwt-symbolmaps"
SYMBOL_MAP="${CACHE_DIR}/${HASH}.symbolMap"

mkdir -p "$CACHE_DIR"

# Download if not cached
if [ ! -f "$SYMBOL_MAP" ]; then
  gsutil cp "gs://lender-rate/c/WEB-INF/deploy/moso/symbolMaps/${HASH}.symbolMap" "$SYMBOL_MAP"
fi

# Auto-clear: keep only the 5 most recent files
ls -t "${CACHE_DIR}"/*.symbolMap 2>/dev/null | tail -n +6 | xargs rm -f
```

Cache dir is `~tmp/gwt-symbolmaps/` (persistent across sessions, survives restarts unlike `/tmp/` root).
Old files beyond the 5 most recent are deleted automatically after each download.

### Step 3: Extract obfuscated symbols from the stack trace

Stack frames look like:
```
Unknown.rL(Unknown Source:75)
Unknown.$BA(Unknown Source:2548)
```

Extract the symbol between `Unknown.` and `(` — e.g. `rL`, `$BA`, `Djm`.

Skip GWT framework frames that aren't useful:
- `com.google.gwt.*`
- `java.lang.Throwable`, `java.lang.Exception`, `java.lang.RuntimeException`, `java.lang.IllegalStateException`

### Step 4: Lookup each symbol

```bash
# For each symbol, look it up in the symbol map
# Symbol map format: jsName,javaSignature,className,memberName,sourceFile,sourceLine,jsniField
grep "^SYMBOL," "${CACHE_DIR}/${HASH}.symbolMap" | head -1
```

Note: `$` in symbol names must be escaped or quoted properly in grep.

### Step 5: Format the decoded stack trace

Output a clean, readable stack trace like:

```
java.lang.IllegalStateException: <error message>
  at com.mvu.loan.shared.LoanUtils.isRequiredLenderProcessing(LoanUtils.java:2547)  ← ROOT CAUSE
  at com.mvu.loan.client.view.application.loan_summary.LenderAndCompensationSectionBuilder$4.$lambda$0(LenderAndCompensationSectionBuilder.java:263)
  at com.mvu.loan.client.view.application.CompensationDataProvider.$loadLenderInfo(CompensationDataProvider.java:113)
  at com.mvu.loan.client.view.application.details.new_wizard._1003FormManager.$lambda$21(_1003FormManager.java:378)
  at com.mvu.core.client.RemoteDataLoader.$processData(RemoteDataLoader.java:126)
  at com.mvu.core.client.form.Form.$setValues(Form.java:514)
  at com.mvu.core.client.BaseCallback.$onSuccess(BaseCallback.java:56)
  at com.mvu.core.client.RemoteCall$2.onResponseReceived(RemoteCall.java:247)
  [GWT framework frames omitted]
```

Then add a **Root Cause Summary**:
- Which class and method threw
- What the error message says (NPE, IllegalState, etc.)
- The call chain in plain English (e.g. "API response came back → form updated → watcher fired → X called Y with null")

## Tips

- Symbol map lines starting with `#` are comments — skip them
- Some symbols won't be found (anonymous JS, browser internals) — mark as `[native]`
- The caused-by exception is usually more useful than the outer wrapper
- `com.mvu.*` frames are application code — prioritize those in the summary
- Filter out pure GWT/Java runtime bootstrap frames for readability
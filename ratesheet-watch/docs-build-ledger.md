# SDD ledger — plan: /Users/trungthach/IdeaProjects/moso-docs/docs/plans/2026-08-13-ratesheet-watch-implementation.md
Branch: ratesheet-watch (tools repo, created from main @ 786248f)
Task 1: fix round 1/5 (3 addressed, 0 open — adj variant coverage, unused import, type annotations; commits f9b19ec..54750b0)
Task 1: complete (commits 786248f..54750b0, review clean)
Task 1: minor (deferred): commit subject 74 chars vs 72 guideline — cosmetic, not refixing
Task 2: complete (commits 54750b0..fb922c6, review clean)
Task 2: minor (deferred): NUM_RE misses leading-dot decimals like .375 — a rate row of bare .375-style values would evade masking; revisit if a lender fixture hits it
Task 2: note: Homebridge PDF is text-extractable; promo banners captured verbatim (validates Stage-1 approach)
Task 3: fix round 1/5 (2 addressed, 0 open — numeric-merged-cell test pinned, anchor comment; commits e309242..29bfa7b)
Task 3: complete (commits fb922c6..29bfa7b, review clean; plan wording for merge rule corrected in moso-docs)
Task 3: minor (deferred): theme/indexed fills invisible to heuristic (fgColor.rgb None); FF000000 solid black counts as filled — revisit if a real lender fixture misclassifies
Task 4: fix round 1/5 (adjudicated: churn LAYOUT trigger reinstated with len(s_old)>=10 guard; plan updated; commits 0876d46..408e369)
Task 4: fix round 2/5 (3 addressed, 0 open — PROGRAM materiality high on structure lines + tests, comment fix; commits 408e369..6eb0c8d)
Task 4: complete (commits 29bfa7b..6eb0c8d, review clean)
Task 4: minor (deferred): no test asserts diff() ignores the source key (structural today)
Task 5: complete (commits 6eb0c8d..aa6bf24, review clean; adjudicated in-flight: pending check added to unchanged fast-path per spec prose — plan code had the bug)
Task 5: minor (deferred): duplicate-SHA path never updates the dupe entry's state.sha/date — roles can drift if primary errors while dupe succeeds
Task 5: minor (deferred): bootstrap=True path untested by unit tests (exercised manually in Task 8)
Task 6: complete (commits aa6bf24..5afb1c4, review clean)
Task 6: minor (deferred): _claude_runner has no try/except (sweep catch-all is the only net); _parse_json_array greedy regex can over-capture — add comment/hardening in a follow-up
Task 6: note: brief prose said --max-turns 1/--output-format text but Step-3 code (implemented) uses --max-turns 8; code governs
Task 7: complete (tools commit 5afb1c4..fdefdda; packs Java test staged uncommitted pending MOSO key, review clean)
Task 7: minor (open, folded into Task 8): unused java.io.InputStream import in RatesheetFingerprintTest.java — remove before packs commit
Task 8: fix round 1/5 (3 adjudicated fixes all landed — certifi CA pin, section normalization, error-page rejection + re-bootstrap; commits fdefdda..439f9ea)
Task 8: complete (tools commits 15e0b6c+439f9ea; cron installed 12:30 M-F; 4 pilot fingerprints staged in packs awaiting MOSO key; review clean)
Task 8: minor (deferred): certifi unpinned in requirements.txt; enums_by_norm silently overwrites on normalized collision (none exist today)
Task 8: USER-FACING FINDING: HomeBridgeWholesale has no GCS object under the standard naming — sweep reports it in errors bucket daily; needs user decision (email-only lender? different GCS name?)
Task 9: fix round 1/5 (1 addressed — unmatched glob guard; commits 203c55a..d80ea7d)
Task 9: complete (commits 439f9ea..d80ea7d, review clean; /ratesheet-change skill registered via symlink)
All tasks complete — final whole-branch review next. MERGE_BASE=786248f
Final review: FINDINGS (4 Important) → one fix wave (f56d933, e808406, 9fad23f) → scoped re-review: all 6 ADDRESSED, none open
Final: parked — DATE_RE clock-time pattern could false-mask "80:20"-style ratios in banners — ruling: acceptable, deterministic (masks the same way every day, so no false diffs); revisit if a real promo hinges on a colon ratio
Final: 37/37 tests; pilot fingerprints regenerated timestamp-free and staged in packs; branch ratesheet-watch @ 9fad23f COMPLETE
Open items for user: (1) MOSO key for packs commit, (2) merge tools branch → main, (3) HomeBridgeWholesale GCS naming decision

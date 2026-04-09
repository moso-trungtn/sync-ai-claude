---
name: Always run both RateParserTest and AdjustmentParsersTest for parser fixes
description: When fixing a lender parser, MUST run both RateParserTest and AdjustmentParsersTest for that lender before and after the fix
type: feedback
---

When fixing a lender parser, ALWAYS run BOTH `RateParserTest#test<Lender>()` AND `AdjustmentParsersTest#test<Lender>()` — before making any fix AND after the fix.

**Why:** Rate and adjustment parsers share the same ratesheet and are tightly coupled. A ratesheet layout change (e.g., new pages inserted) can break both parsers simultaneously. Fixing only one test and ignoring the other leads to incomplete fixes that the user has to catch manually. The user has corrected this multiple times.

**How to apply:** In any parser fix workflow (/fix-parser, parser-dev agent, or manual fix):
1. Run both tests BEFORE touching code — understand the full failure picture
2. Fix the code
3. Run both tests AFTER the fix — confirm nothing is left broken
4. Never declare a fix complete with only one test passing

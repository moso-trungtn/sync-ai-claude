---
name: Always update test inputStream references when downloading new ratesheets
description: After downloading a new ratesheet, must update AdjustmentParsersTest.java and RateParserTest.java to use the new RatesheetFiles constant
type: feedback
---

When downloading a new ratesheet for a lender, ALWAYS update the test file references (`inputStream` / `mergedInputStream`) in both `AdjustmentParsersTest.java` and `RateParserTest.java` to use the new `RatesheetFiles.<NEW_CONSTANT>`.

**Why:** The `download-ratesheet.sh` script adds a new constant to `RatesheetFiles.java` but the test methods still point to the old constant. Without updating the test references, the tests run against the OLD ratesheet and will either pass incorrectly or skip, masking real failures.

**How to apply:** After every `download-ratesheet.sh` call, grep for the lender name in both test files, find the `RatesheetFiles.<OLD>` reference, and replace it with the new constant. Then run both tests without `--ratesheet` flag to verify they use the embedded reference correctly.

---
name: check-mail-trigger
description: Use when a lender's ratesheet email stopped producing a parser build — "lender X không trigger email", "mail forward mà không chạy", "sao parser X không chạy hôm nay", "lender mới onboard mail không vào", or after onboarding a lender to confirm its mail actually routes. Also for the fleet question "lender nào đang câm". Walks the five layers an inbound lender email passes through (delivery, routing, lender flag, attachment selection, build) and names the broken one with the log line that proves it.
argument-hint: "[LenderType name, e.g. Newfi] — omit to sweep every lender instead"
allowed-tools: Bash, Read, Edit, Grep, Glob
---

# Check a lender's mail trigger

An inbound lender email crosses five layers. Each one can drop it **silently**: no build, no Jira, no alert.
Always identify the layer from evidence before touching code. Guessing wrong here costs a day.

| Layer | What breaks | Signature in the GAE log |
|---|---|---|
| 1 delivery | mail never reaches the app | `Could not handle email ... Early EOF`, and **no** `Received mailed` line |
| 2 routing | arrives, `LenderMailHandler` matches nothing | `Unknown email from` + `Could not find any lenders with queryBuilder` |
| 3 lender flag | matched but `Lender.has_rate` is false | `Lender 'X' is inactive` |
| 4 attachment | build starts, parser takes no sheet | `Run new<Parser>` present, ratesheet slot unchanged |
| 5 build | build starts and fails | ratesheet slot unchanged, builder reports the error |

## Run it

From `packs/loan`:

```bash
./mail-trigger-diagnose.sh <LenderType> [--days N] [--staging]   # one lender, prints a verdict
./mail-trigger-check.sh [--days N] [--staging] [--all]           # fleet sweep: who is silent
```

The log step needs `gcloud auth application-default print-access-token` to work. If it does not, run
`gcloud auth application-default login`; without it the script still prints the GCS evidence.
Prod project is `lender-rate`, staging is `lenderrate-master`.

## Reading the verdict

**Layer 1, not delivered.** Big mails die in Google's mail bridge on the Jetty 12 runtime, before any of our
code runs, so nothing can be fixed in the parser. Confirm the mail was actually sent, then ask the AE to send
the sheet without the heavyweight extras, or give the parser its own download. Do not add buffering or
streaming code in `MailProcessor`; large POST bodies to other endpoints work fine, so the app is not the
problem.

**Layer 2, routing.** The most common cause, and it rots over time: clauses match a substring of the subject,
and lenders reword subjects constantly. Read the exact `Subject` and `From` the script printed, then fix the
clause in `LenderMailHandler`:

- Prefer `from.contains("@lenderdomain.com")`. The domain is stable; the subject is marketing copy.
- Both relay groups rewrite `From` to `'<Lender Name>' via Rate <rates@…>`, so when the domain is gone match
  the display name: `from.toLowerCase().contains("<lender>")`. `from` is **not** lower-cased upstream.
- Never match a generic phrase alone (`daily rate sheet`, `today's rates`). Require a second signal, or scope
  it to hand-forwards with `manuallyForward`.
- Order is load-bearing, first match wins. A generic clause placed high steals other lenders' mail.
- Add a case to `LenderMailHandlerRoutingTest` using the real subject and From from the log.

**Layer 3, lender flag.** Not a code change. Switch the lender on in admin.

**Layer 4, attachment.** The parser's own gate rejected the file. Select by **attachment filename**, which is
specific, not by subject wording, which is whatever a human typed when forwarding. Check the `Files` line the
script printed against the parser's rules.

**Layer 5, build.** Open the build log on the builder named in the `Response` line. A Non-QM channel that was
never given a ratesheet source fails here every time: check that something actually writes
`<Lender>NonQM.<ext>` to the ratesheet bucket.

## After fixing

Run the routing test, and re-run the diagnose script against staging once the change is deployed. Bump
`LenderMailHandler.HEX` when you edit that file so the deployed version is identifiable in the log line
`File version: …`.

Background and past cases: `project_lender_mail_routing_silently_rots` and
`project_gae_jetty12_early_eof_drops_large_lender_mail` in memory.

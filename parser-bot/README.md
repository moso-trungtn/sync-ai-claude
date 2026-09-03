# Parser Bot

Triage overnight lender parse failures in Google Chat; fix only on `@Parser Bot fix <lender>`.
Spec: `docs/superpowers/specs/2026-09-03-parser-bot-design.md`. Plan: `docs/superpowers/plans/2026-09-03-parser-bot.md`.

## One-time setup (human)

1. LF bot account: create admin `parser-bot@loanfactory.com` with owner permission; save
   `~/.config/parser-bot/lf.json` = `{"username": "parser-bot@loanfactory.com", "password": "..."}`; `chmod 600`.
2. Jira: `~/.config/parser-bot/env` with `JIRA_EMAIL=...` and `JIRA_API_TOKEN=...`; `chmod 600`.
3. GCP (needs `gcloud auth login` first):
   ```bash
   gcloud config set project lenderrate-master
   gcloud services enable chat.googleapis.com pubsub.googleapis.com
   gcloud pubsub topics create parser-bot-events
   gcloud pubsub topics add-iam-policy-binding parser-bot-events \
     --member=serviceAccount:chat-api-push@system.gserviceaccount.com --role=roles/pubsub.publisher
   gcloud pubsub subscriptions create parser-bot-sub --topic=parser-bot-events --ack-deadline=60
   gcloud iam service-accounts create parser-bot --display-name="Parser Bot"
   gcloud pubsub subscriptions add-iam-policy-binding parser-bot-sub \
     --member=serviceAccount:parser-bot@lenderrate-master.iam.gserviceaccount.com --role=roles/pubsub.subscriber
   mkdir -p ~/.config/parser-bot && gcloud iam service-accounts keys create ~/.config/parser-bot/sa.json \
     --iam-account=parser-bot@lenderrate-master.iam.gserviceaccount.com && chmod 600 ~/.config/parser-bot/sa.json
   ```
4. Chat app (console → APIs & Services → Google Chat API → Configuration): name `Parser Bot`, description
   `Triage and fix ratesheet parser failures`, avatar any HTTPS PNG, **uncheck** "Build this Chat app as a Google
   Workspace add-on", Functionality: "Join spaces and group conversations", Connection settings: Cloud Pub/Sub,
   topic `projects/lenderrate-master/topics/parser-bot-events`, Visibility: specific people/groups (Trung + IT),
   Log errors to Logging. Save. Then in the Parser Alerts space: Apps & integrations → Add apps → Parser Bot.
5. Config: `cp config.example.yaml ~/.config/parser-bot/config.yaml` and edit if paths differ.
6. Clones + index: `./setup_clones.sh && ./refresh_clones.sh` and
   `.venv/bin/python -m parser_bot.lenders /Users/trungthach/IdeaProjects/packs/quote/src/main/java/com/mvu/quote/shared/typekey/LenderType.java state/lenders.json`.

## Run

- Smoke test (no posting, no Jira, no claude): `./run.sh --once --dry-run --no-listener --force-window`
- One real poll + pull: `./run.sh --once --force-window`
- Daemon: `cp launchd/com.loanfactory.parser-bot.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.loanfactory.parser-bot.plist`
- Logs: `logs/bot.log`, `logs/bot.err`. State: `state/<night>.json`.
- Stop: `launchctl unload ~/Library/LaunchAgents/com.loanfactory.parser-bot.plist`

## Phase A → B

Phase A: `commands_enabled: false`; the bot only triages. After ~1 week of correct causes, set
`commands_enabled: true` and `launchctl unload && launchctl load`. Commands: `@Parser Bot fix <lender>`,
`fix all`, `skip <lender>`, `retry <lender>`, `status`.

import os
import textwrap
from parser_bot.config import load_config


def test_load_config_expands_paths_and_applies_defaults(tmp_path):
    cfg_file = tmp_path / "c.yaml"
    cfg_file.write_text(textwrap.dedent("""
        space: spaces/X
        lf: {base_url: https://lf, ns: LOAN_FACTORY, credentials_file: ~/lf.json}
        jira: {base_url: https://j, email_env: JE, token_env: JT, project: MOSO, assignee_account_id: "1:2"}
        gcp: {subscription: projects/p/subscriptions/s, service_account_file: ~/sa.json}
        paths: {bot_root: /bot, state_dir: /st, cookbook: /cb.md, report_dir: tmp/pf, lenders_json: /l.json, aliases: /a.yaml, gcs_bucket: b}
        schedule: {timezone: Asia/Ho_Chi_Minh, poll_start: "19:30", poll_end: "05:30", poll_interval_sec: 60, lookback_hours: 6}
        timeouts: {triage_sec: 10, fix_sec: 20, prepare_sec: 30}
    """))
    cfg = load_config(str(cfg_file))
    assert cfg.space == "spaces/X"
    assert cfg.lf_credentials_file.startswith("/") and cfg.lf_credentials_file.endswith("/lf.json")
    assert cfg.gcp_service_account_file.endswith("/sa.json") and "~" not in cfg.gcp_service_account_file
    assert cfg.commands_enabled is False          # default when missing
    assert cfg.allowlist == []                    # default when missing
    assert cfg.poll_interval_sec == 60 and cfg.fix_sec == 20 and cfg.lookback_hours == 6
    assert cfg.listener_idle_sec == 2             # default when schedule.listener_idle_sec is missing
    assert cfg.jira_assignee == "1:2"
    assert os.path.isabs(cfg.report_dir) and cfg.report_dir.endswith("/tmp/pf")


def test_chat_webhook_url_defaults_to_empty_and_reads_chat_section(tmp_path):
    base = textwrap.dedent("""
        space: spaces/X
        lf: {base_url: https://lf, ns: LOAN_FACTORY, credentials_file: ~/lf.json}
        jira: {base_url: https://j, email_env: JE, token_env: JT, project: MOSO, assignee_account_id: "1:2"}
        gcp: {subscription: projects/p/subscriptions/s, service_account_file: ~/sa.json}
        paths: {bot_root: /bot, state_dir: /st, cookbook: /cb.md, report_dir: /tmp/pf, lenders_json: /l.json, aliases: /a.yaml, gcs_bucket: b}
        schedule: {timezone: Asia/Ho_Chi_Minh, poll_start: "19:30", poll_end: "05:30", poll_interval_sec: 60, lookback_hours: 6}
        timeouts: {triage_sec: 10, fix_sec: 20, prepare_sec: 30}
    """)
    f = tmp_path / "c.yaml"
    f.write_text(base)
    assert load_config(str(f)).chat_webhook_url == ""
    f.write_text(base + "chat: {webhook_url: 'https://chat.googleapis.com/v1/spaces/X/messages?key=k&token=t'}\n")
    assert load_config(str(f)).chat_webhook_url.startswith("https://chat.googleapis.com/v1/spaces/X/")

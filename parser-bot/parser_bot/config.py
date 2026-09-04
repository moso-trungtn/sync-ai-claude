"""Typed config loaded from YAML. All paths are expanded to absolute strings."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Config:
    space: str
    lf_base_url: str
    lf_ns: str
    lf_credentials_file: str
    jira_base_url: str
    jira_email_env: str
    jira_token_env: str
    jira_project: str
    jira_assignee: str
    gcp_subscription: str
    gcp_service_account_file: str
    bot_root: str
    state_dir: str
    cookbook: str
    report_dir: str
    lenders_json: str
    aliases: str
    gcs_bucket: str
    timezone: str
    poll_start: str
    poll_end: str
    poll_interval_sec: int
    lookback_hours: int
    triage_sec: int
    fix_sec: int
    prepare_sec: int
    listener_idle_sec: int = 2
    commands_enabled: bool = False
    allowlist: list[str] = field(default_factory=list)
    chat_webhook_url: str = ""

    @property
    def moso_pricing(self) -> str:
        return os.path.join(self.bot_root, "moso-pricing")

    @property
    def packs_loan(self) -> str:
        return os.path.join(self.bot_root, "packs", "loan")


def _p(value: str) -> str:
    return os.path.abspath(os.path.expanduser(value))


def load_config(path: str) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    lf, jira, gcp, paths = raw["lf"], raw["jira"], raw["gcp"], raw["paths"]
    sched, to = raw["schedule"], raw["timeouts"]
    return Config(
        space=raw["space"],
        lf_base_url=lf["base_url"].rstrip("/"),
        lf_ns=lf["ns"],
        lf_credentials_file=_p(lf["credentials_file"]),
        jira_base_url=jira["base_url"].rstrip("/"),
        jira_email_env=jira["email_env"],
        jira_token_env=jira["token_env"],
        jira_project=jira["project"],
        jira_assignee=str(jira["assignee_account_id"]),
        gcp_subscription=gcp["subscription"],
        gcp_service_account_file=_p(gcp["service_account_file"]),
        bot_root=_p(paths["bot_root"]),
        state_dir=_p(paths["state_dir"]),
        cookbook=_p(paths["cookbook"]),
        report_dir=_p(paths["report_dir"]),
        lenders_json=_p(paths["lenders_json"]),
        aliases=_p(paths["aliases"]),
        gcs_bucket=paths["gcs_bucket"],
        timezone=sched["timezone"],
        poll_start=str(sched["poll_start"]),
        poll_end=str(sched["poll_end"]),
        poll_interval_sec=int(sched["poll_interval_sec"]),
        lookback_hours=int(sched.get("lookback_hours", 6)),
        triage_sec=int(to["triage_sec"]),
        fix_sec=int(to["fix_sec"]),
        prepare_sec=int(to["prepare_sec"]),
        listener_idle_sec=int(sched.get("listener_idle_sec", 2)),
        commands_enabled=bool(raw.get("commands_enabled", False)),
        allowlist=list(raw.get("allowlist", []) or []),
        chat_webhook_url=str((raw.get("chat") or {}).get("webhook_url", "") or ""),
    )

"""Wiring: poll LF for failures → triage → Chat; Pub/Sub commands → fix → Chat + Jira."""
from __future__ import annotations

import argparse
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta

from . import messages
from .chat import ChatClient
from .commands import Command, parse_event
from .config import Config, load_config
from .fixer import Fixer, FixResult
from .jira import JiraClient
from .lenders import LenderIndex, load_index
from .lf_api import LFClient
from .nights import ICT, ict_clock, in_window, night_id, pacific_date
from .state import (AWAITING_CONFIRM, FIX_FAILED, FIXED, FIXING, NOT_CODE, SKIPPED, TRIAGED, LenderState, NightState)
from .triage import Triager, TriageResult, channel_of

log = logging.getLogger("parser-bot")


class Bot:
    def __init__(self, cfg: Config, lf, chat, jira, triager, fixer, lenders: LenderIndex, now=None, dry_run: bool = False):
        self.cfg, self.lf, self.chat, self.jira, self.triager, self.fixer, self.lenders = cfg, lf, chat, jira, triager, fixer, lenders
        self.now = now or (lambda: datetime.now(tz=ICT))
        self.dry_run = dry_run
        self.fix_lock = threading.Lock()

    # ---- helpers -------------------------------------------------------------------------------
    def state(self) -> NightState:
        return NightState.load(self.cfg.state_dir, night_id(self.now()))

    def _post(self, text: str, thread_key: str | None = None, thread_name: str | None = None) -> str:
        if self.dry_run:
            log.info("[dry-run] would post (%s): %s", thread_key or thread_name, text)
            return ""
        return (self.chat.post(text, thread_key=thread_key, thread_name=thread_name).get("thread") or {}).get("name", "")

    def _sheet_uri(self, res: TriageResult) -> str:
        if not res.sheet:
            return ""
        d = self.now().astimezone(ICT).date()
        name = res.lender + ("NonQM" if res.channel == "NonQM" else "")
        return f"gs://{self.cfg.gcs_bucket}/history/{name}/{d:%Y}/{d:%m}/{d:%d}/ ({os.path.basename(res.sheet)})"

    # ---- poller --------------------------------------------------------------------------------
    def poll_once(self) -> list[TriageResult]:
        now = self.now()
        st = self.state()
        failures = self.lf.failures_since(now - timedelta(hours=self.cfg.lookback_hours))
        fresh = [f for f in failures if st.mark_seen(f.key)]
        st.save()
        results: list[TriageResult] = []
        if fresh and not st.prepared:
            self.triager.prepare_night(st)   # pull clones + mvn install moso-pricing, once per night
        for f in fresh:
            channel = channel_of(f)
            k = st.key(f.lender, channel)
            if k in st.lenders:
                continue  # one thread per lender+channel per night; later zone builds are noise
            res = self.triager.triage(f)
            label = self.lenders.label(f.lender)
            text = messages.triage_text(res, label, ict_clock(now), self._sheet_uri(res))
            thread = self._post(text, thread_key=f"{f.lender}-{now.astimezone(ICT):%m-%d}")
            status = TRIAGED if res.classification.cls == "LAYOUT" else NOT_CODE
            st.lenders[k] = LenderState(lender=f.lender, channel=channel, status=status, detected_at=now.isoformat(),
                                        reason=f.description, cause=res.classification.cause, cls=res.classification.cls,
                                        error_type=res.classification.error_type, tier=res.tier, streak=res.streak,
                                        sheet=res.sheet, thread_name=thread)
            st.save()
            results.append(res)
        return results

    # ---- commands ------------------------------------------------------------------------------
    def _find(self, st: NightState, text: str) -> tuple[LenderState | None, str]:
        r = self.lenders.resolve(text)
        if r.kind != "one":
            return None, messages.unknown_lender_text(text, r.matches)
        hits = [ls for ls in st.lenders.values() if ls.lender == r.matches[0]]
        if not hits:
            return None, messages.unknown_lender_text(text, [])
        return hits[0], ""

    def handle_command(self, cmd: Command) -> str:
        st = self.state()
        if cmd.kind == "status":
            return messages.status_text(st, {e: self.lenders.label(e) for e in {ls.lender for ls in st.lenders.values()}})
        if cmd.kind == "fix_all":
            targets = [ls for ls in st.lenders.values() if ls.status in (TRIAGED, AWAITING_CONFIRM, FIX_FAILED)]
            if not targets:
                return "Nothing to fix tonight."
            return "\n".join(self._fix(st, ls) for ls in targets)
        ls, err = self._find(st, cmd.lender_text)
        if not ls:
            return err
        if cmd.kind == "skip":
            ls.status = SKIPPED
            st.save()
            return f"Skipped {self.lenders.label(ls.lender)} for tonight."
        return self._fix(st, ls)  # fix | retry

    def _fix(self, st: NightState, ls: LenderState) -> str:
        label = self.lenders.label(ls.lender)
        if not self.cfg.commands_enabled:
            return messages.disabled_text()
        if ls.status == NOT_CODE:
            return f"{label}: {ls.cause}. Not a parser problem, nothing to fix."
        if ls.status in (FIXING, FIXED):
            return f"{label} is already {ls.status.lower()}" + (f" on branch {ls.branch}." if ls.branch else ".")
        if self.dry_run:
            return f"[dry-run] would fix {label}"
        with self.fix_lock:
            key = self.jira.ensure_ticket(st, label, pacific_date(self.now()))
            ls.status = FIXING
            st.save()
            fix: FixResult = self.fixer.run(ls.lender, key)
            ls.branch = fix.branch or key
            if fix.status == "fixed":
                ls.status, text = FIXED, messages.result_text(label, fix, key)
            else:
                ls.status, text = FIX_FAILED, messages.failure_text(label, fix, key)
            ls.notes = fix.notes
            st.save()
            self.jira.comment(key, self._jira_comment(label, ls, fix))
            return text

    @staticmethod
    def _jira_comment(label: str, ls: LenderState, fix: FixResult) -> str:
        body = [f"h3. {label} ({ls.channel})", f"* Cause: {ls.error_type} — {ls.cause}", f"* Tier: {fix.tier or ls.tier}",
                f"* Status: {fix.status}", f"* Branch: {fix.branch}", f"* Files: {', '.join(fix.files) or '-'}",
                f"* Tests: {json.dumps(fix.tests)}", f"* Notes: {fix.notes or '-'}"]
        if fix.raw_tail:
            body += ["{code}", fix.raw_tail[-1500:], "{code}"]
        return "\n".join(body)

    # ---- loops ---------------------------------------------------------------------------------
    def listen_once(self) -> None:
        from .pubsub import pull_events
        for ev in pull_events(self.cfg.gcp_subscription, self.cfg.gcp_service_account_file):
            cmd = parse_event(ev)
            if not cmd:
                continue
            if self.cfg.allowlist and cmd.sender_email not in self.cfg.allowlist:
                self._post(f"Sorry {cmd.sender_name}, you are not on the allowlist.", thread_name=cmd.thread_name)
                continue
            log.info("command %s from %s", cmd, cmd.sender_email)
            try:
                reply = self.handle_command(cmd)
            except Exception as e:  # never let one command kill the loop
                log.exception("command failed")
                reply = f"Command failed: {e}"
            self._post(reply, thread_name=cmd.thread_name or None)

    def run(self, once: bool = False, listener: bool = True) -> None:
        last_poll = 0.0
        while True:
            now = self.now()
            if in_window(now, self.cfg.poll_start, self.cfg.poll_end) and time.time() - last_poll >= self.cfg.poll_interval_sec:
                try:
                    self.poll_once()
                except Exception:
                    log.exception("poll failed")
                last_poll = time.time()
            if listener:
                try:
                    self.listen_once()
                except Exception:
                    log.exception("listener failed")
                    time.sleep(10)
            if once:
                return
            if not listener:
                time.sleep(min(30, self.cfg.poll_interval_sec))


def build_bot(cfg: Config, dry_run: bool) -> Bot:
    creds = json.loads(open(cfg.lf_credentials_file, encoding="utf-8").read())
    lf = LFClient(cfg.lf_base_url, cfg.lf_ns, creds["username"], creds["password"])
    chat = ChatClient(cfg.gcp_service_account_file, cfg.space)
    jira = JiraClient(cfg.jira_base_url, os.environ[cfg.jira_email_env], os.environ[cfg.jira_token_env],
                      cfg.jira_project, cfg.jira_assignee)
    return Bot(cfg, lf, chat, jira, Triager(cfg), Fixer(cfg), load_index(cfg.lenders_json, cfg.aliases), dry_run=dry_run)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="parser-bot")
    ap.add_argument("--config", default=os.path.expanduser("~/.config/parser-bot/config.yaml"))
    ap.add_argument("--once", action="store_true", help="one poll + one pull, then exit")
    ap.add_argument("--dry-run", action="store_true", help="never post, never create Jira, never run claude")
    ap.add_argument("--no-listener", action="store_true")
    ap.add_argument("--force-window", action="store_true", help="poll even outside the active window")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config(args.config)
    if args.force_window:
        cfg.poll_start, cfg.poll_end = "00:00", "23:59"
    build_bot(cfg, args.dry_run).run(once=args.once, listener=not args.no_listener)


if __name__ == "__main__":
    main()

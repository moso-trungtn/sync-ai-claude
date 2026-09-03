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
    def __init__(self, cfg: Config, lf, chat, jira, triager, fixer, lenders: LenderIndex, now=None, dry_run: bool = False,
                 spawn=None):
        self.cfg, self.lf, self.chat, self.jira, self.triager, self.fixer, self.lenders = cfg, lf, chat, jira, triager, fixer, lenders
        self.now = now or (lambda: datetime.now(tz=ICT))
        self.dry_run = dry_run
        self.fix_lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.spawn = spawn or (lambda fn: threading.Thread(target=fn, daemon=True).start())

    # ---- helpers -------------------------------------------------------------------------------
    def state(self) -> NightState:
        return NightState.load(self.cfg.state_dir, night_id(self.now()))

    def _update(self, fn):
        """Load → mutate → save under state_lock, as one short critical section.

        No NightState instance may be held across triage(), prepare_night(), fixer.run(), or a
        chat.post() call — those can each take seconds to minutes, and NightState.save() is a
        full-snapshot overwrite, so holding one that long would silently discard whatever the
        other thread (poller vs. command worker) wrote in the meantime.
        """
        with self.state_lock:
            st = self.state()
            result = fn(st)
            st.save()
            return result

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
        failures = self.lf.failures_since(now - timedelta(hours=self.cfg.lookback_hours))
        fresh = self._update(lambda st: [f for f in failures if st.mark_seen(f.key)])
        results: list[TriageResult] = []
        if fresh and not self._update(lambda st: st.prepared):
            self.triager.prepare()                       # minutes of shell work — NO lock, NO state held
            self._update(lambda st: setattr(st, "prepared", True))
        for f in fresh:
            channel = channel_of(f)
            k = NightState.key(f.lender, channel)
            if self._update(lambda st, k=k: k in st.lenders):
                continue  # one thread per lender+channel per night; later zone builds are noise
            res = self.triager.triage(f)   # no state held — this is the slow part
            label = self.lenders.label(f.lender)
            text = messages.triage_text(res, label, ict_clock(now), self._sheet_uri(res))
            thread = self._post(text, thread_key=f"{f.lender}-{night_id(now)[5:]}")

            def _set(st, k=k, f=f, channel=channel, status=(TRIAGED if res.classification.cls == "LAYOUT" else NOT_CODE),
                     res=res, thread=thread):
                st.lenders[k] = LenderState(lender=f.lender, channel=channel, status=status, detected_at=now.isoformat(),
                                            reason=f.description, cause=res.classification.cause, cls=res.classification.cls,
                                            error_type=res.classification.error_type, tier=res.tier, streak=res.streak,
                                            sheet=res.sheet, thread_name=thread)
            self._update(_set)
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
        if cmd.kind == "status":
            st = self.state()
            return messages.status_text(st, {e: self.lenders.label(e) for e in {ls.lender for ls in st.lenders.values()}})
        if cmd.kind == "fix_all":
            return self._start_fix_all()
        st = self.state()
        ls, err = self._find(st, cmd.lender_text)
        if not ls:
            return err
        key = NightState.key(ls.lender, ls.channel)
        if cmd.kind == "skip":
            self._update(lambda st, key=key: setattr(st.lenders[key], "status", SKIPPED))
            return f"Skipped {self.lenders.label(ls.lender)} for tonight."
        label = self.lenders.label(ls.lender)
        gate = self._fix_gate(ls, label)
        if gate is not None:
            return gate
        return self._start_fix(key, cmd.thread_name)  # fix | retry

    def _fix_gate(self, ls: LenderState, label: str) -> str | None:
        """Synchronous eligibility checks, run before ever touching the fixer/lock."""
        if not self.cfg.commands_enabled:
            return messages.disabled_text()
        if ls.status == NOT_CODE:
            return f"{label}: {ls.cause}. Not a parser problem, nothing to fix."
        if ls.status == FIXED:
            return f"{label} is already fixed" + (f" on branch {ls.branch}." if ls.branch else ".")
        if self.dry_run:
            return f"[dry-run] would fix {label}"
        return None

    def _busy_label(self, st: NightState, ls: LenderState) -> str:
        if ls.status == FIXING:
            return self.lenders.label(ls.lender)
        other = next((o for o in st.lenders.values() if o.status == FIXING), None)
        return self.lenders.label(other.lender if other else ls.lender)

    def _start_fix(self, state_key: str, thread_name: str | None) -> str:
        def _mark(st):
            ls = st.lenders[state_key]
            if ls.status == FIXING or self.fix_lock.locked():
                return "busy", self._busy_label(st, ls)
            ls.status = FIXING
            return "ok", (self.lenders.label(ls.lender), ls.tier, ls.thread_name)

        kind, payload = self._update(_mark)
        if kind == "busy":
            return messages.busy_text(payload)
        label, tier, ls_thread_name = payload
        self.spawn(lambda: self._run_fix(state_key, thread_name or ls_thread_name))
        return messages.fixing_text(label, tier)

    def _start_fix_all(self) -> str:
        def _mark_all(st):
            targets = [ls for ls in st.lenders.values() if ls.status in (TRIAGED, AWAITING_CONFIRM, FIX_FAILED)]
            if not targets:
                return None
            acks, keys = [], []
            for ls in targets:
                label = self.lenders.label(ls.lender)
                gate = self._fix_gate(ls, label)
                if gate is not None:
                    acks.append(gate)
                    continue
                ls.status = FIXING
                acks.append(messages.fixing_text(label, ls.tier))
                keys.append(NightState.key(ls.lender, ls.channel))
            return acks, keys

        result = self._update(_mark_all)
        if result is None:
            return "Nothing to fix tonight."
        acks, keys = result
        if keys:
            # ONE worker walks every eligible lender sequentially — each _run_fix(k, None) posts
            # into that lender's own triage thread (thread_name resolves to ls.thread_name).
            self.spawn(lambda keys=keys: [self._run_fix(k, None) for k in keys])
        return "\n".join(acks)

    def _run_fix(self, state_key: str, thread_name: str | None) -> None:
        label = state_key   # fallback if we crash before resolving the real label below
        with self.fix_lock:
            try:
                lender = state_key.split("|", 1)[0]
                label = self.lenders.label(lender)

                def _prep(st):
                    ls = st.lenders[state_key]
                    key = self.jira.ensure_ticket(st, label, pacific_date(self.now()))
                    return ls.channel, ls.tier, ls.cause, ls.error_type, ls.thread_name, key

                channel, tier, cause, error_type, thread, key = self._update(_prep)
                fix: FixResult = self.fixer.run(lender, key)   # no state held — this is the slow part

                def _apply(st):
                    ls = st.lenders[state_key]
                    ls.branch = fix.branch or key
                    ls.status = FIXED if fix.status == "fixed" else FIX_FAILED
                    ls.notes = fix.notes
                    return ls.status

                status = self._update(_apply)
                text = messages.result_text(label, fix, key) if status == FIXED else messages.failure_text(label, fix, key)
                self.jira.comment(key, self._jira_comment(label, channel, error_type, cause, tier, fix))
                self._post(text, thread_name=thread_name or thread or None)
            except Exception as e:
                log.exception("fix worker failed for %s", state_key)
                try:
                    def _fail(st, e=e):
                        ls = st.lenders.get(state_key)
                        if ls is not None:
                            ls.status = FIX_FAILED
                            ls.notes = str(e)
                    self._update(_fail)
                except Exception:
                    log.exception("could not record fix failure for %s", state_key)
                try:
                    self._post(f"❌ *{label}* fix crashed: {e}", thread_name=thread_name or None)
                except Exception:
                    log.exception("could not post crash message for %s", state_key)

    @staticmethod
    def _jira_comment(label: str, channel: str, error_type: str, cause: str, tier: str, fix: FixResult) -> str:
        body = [f"h3. {label} ({channel})", f"* Cause: {error_type} — {cause}", f"* Tier: {fix.tier or tier}",
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

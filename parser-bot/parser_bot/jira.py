"""One Jira ticket per night. REST v2 with Basic auth; description in wiki markup, English only."""
from __future__ import annotations

import requests

from .state import NightState

PREFIX = "[Parser failed] "


class JiraClient:
    def __init__(self, base_url: str, email: str, token: str, project: str, assignee: str, session=None):
        self.base = base_url.rstrip("/")
        self.project = project
        self.assignee = assignee
        self.session = session or requests.Session()
        self.session.auth = (email, token)

    def _transition(self, key: str, name: str) -> None:
        r = self.session.get(f"{self.base}/rest/api/2/issue/{key}/transitions", timeout=30)
        r.raise_for_status()
        for t in r.json().get("transitions", []):
            if t["name"] == name:
                self.session.post(f"{self.base}/rest/api/2/issue/{key}/transitions",
                                  json={"transition": {"id": t["id"]}}, timeout=30).raise_for_status()
                return

    def create_night_ticket(self, date_pt: str, labels: list[str]) -> str:
        fields = {
            "project": {"key": self.project},
            "issuetype": {"name": "Task"},
            "summary": f"{PREFIX}{date_pt}: {', '.join(labels)}",
            "labels": ["parser"],
            "assignee": {"accountId": self.assignee},
            "description": ("h3. Overnight parser failures\n"
                            "Created by Parser Bot. One comment per lender below: cause, tier, branch, test output.\n"
                            "Fixes live on branch(es) named after this key; review and merge to master manually."),
        }
        r = self.session.post(f"{self.base}/rest/api/2/issue", json={"fields": fields}, timeout=30)
        r.raise_for_status()
        key = r.json()["key"]
        self._transition(key, "Select for development")
        self._transition(key, "Start Progress")
        return key

    def append_lender(self, key: str, label: str) -> None:
        r = self.session.get(f"{self.base}/rest/api/2/issue/{key}", params={"fields": "summary"}, timeout=30)
        r.raise_for_status()
        summary = r.json()["fields"]["summary"]
        head, _, tail = summary.partition(": ")
        names = [n.strip() for n in tail.split(",") if n.strip()] if tail else []
        if label in names:
            return
        names.append(label)
        self.session.put(f"{self.base}/rest/api/2/issue/{key}",
                         json={"fields": {"summary": f"{head}: {', '.join(names)}"}}, timeout=30).raise_for_status()

    def comment(self, key: str, text: str) -> None:
        self.session.post(f"{self.base}/rest/api/2/issue/{key}/comment", json={"body": text}, timeout=30).raise_for_status()

    def ensure_ticket(self, state: NightState, label: str, date_pt: str) -> str:
        if state.ticket:
            self.append_lender(state.ticket, label)
        else:
            state.ticket = self.create_night_ticket(date_pt, [label])
            state.save()
        return state.ticket

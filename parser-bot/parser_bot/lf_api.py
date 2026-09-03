"""Loan Factory EntityAPI client: password-grant token + RateUpdate failures."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

TOKEN_MARGIN_SEC = 300


@dataclass(frozen=True)
class RateFailure:
    key: str
    created: str
    lender: str
    description: str

    def created_at(self) -> datetime | None:
        """When the builder recorded the failure. RateUpdate.created is naive UTC; None if unparsable."""
        raw = (self.created or "").strip()
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class LFClient:
    def __init__(self, base_url: str, ns: str, username: str, password: str, session=None, clock=time.time):
        self.base_url = base_url.rstrip("/")
        self.ns = ns
        self.username = username
        self.password = password
        self.session = session or requests.Session()
        self.clock = clock
        self._token: str | None = None
        self._expires_at = 0.0

    def token(self) -> str:
        if self._token and self.clock() < self._expires_at - TOKEN_MARGIN_SEC:
            return self._token
        r = self.session.post(f"{self.base_url}/api/oauth2/v1/{self.ns}/token",
                              json={"grant_type": "password", "username": self.username, "password": self.password},
                              timeout=30)
        r.raise_for_status()
        body = r.json()
        self._token = body["access_token"]
        self._expires_at = self.clock() + float(body.get("expires_in", 1800))
        return self._token

    def failures_since(self, since: datetime) -> list[RateFailure]:
        since_utc = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")
        r = self.session.get(f"{self.base_url}/api/entity/v1/rate_update",
                             params={"created>": since_utc, "l": "200", "o": "-created"},
                             headers={"Authorization": f"Bearer {self.token()}"}, timeout=60)
        r.raise_for_status()
        out = []
        for row in r.json().get("items", []):
            if row.get("status", True) is not False:
                continue
            out.append(RateFailure(key=str(row.get("key", "")), created=str(row.get("created", "")),
                                   lender=str(row.get("lender", "")), description=str(row.get("description", ""))))
        return out

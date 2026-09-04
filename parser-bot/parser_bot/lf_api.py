"""Loan Factory EntityAPI client: password-grant token + RateUpdate failures."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests

TOKEN_MARGIN_SEC = 300


@dataclass(frozen=True)
class RateFailure:
    key: str
    created: str
    lender: str
    description: str

    def created_at(self) -> datetime | None:
        """Builder timestamp as an aware UTC datetime. Wire format is epoch millis (string); ISO also accepted."""
        raw = (self.created or "").strip()
        if not raw:
            return None
        if raw.isdigit():
            return datetime.fromtimestamp(int(raw) / 1000, tz=timezone.utc)
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
        self._api_key: str | None = None

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

    def api_key(self) -> str:
        """The user's LF API key (stable per user), fetched once with the bearer token."""
        if self._api_key:
            return self._api_key
        r = self.session.post(f"{self.base_url}/api/mobile/v1/{self.ns}/getCurrentUserAPIKey", json={},
                              headers={"Authorization": f"Bearer {self.token()}"}, timeout=30)
        r.raise_for_status()
        self._api_key = r.json()["result"]["api_key"]
        return self._api_key

    def failures_since(self, since: datetime) -> list[RateFailure]:
        """RateUpdate rows with status == false created at/after `since`.

        Uses the namespaced LF IQ API (`execute/FindOp`, x-api-key) because the un-namespaced EntityAPI cannot
        verify tokens minted in the LF namespace. FindOp accepts a day-granular `created` range (server-local
        midnights) and cannot combine it with a `status` filter (no composite index), so we ask for a wide day
        window and filter status and the exact `since` instant client-side.
        """
        since_utc = since.astimezone(timezone.utc)
        start = (since_utc - timedelta(days=1)).strftime("%Y-%m-%d")
        end = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
        r = self.session.post(f"{self.base_url}/api/lfiq/v1/{self.ns}/execute/FindOp",
                              json={"kind": "RateUpdate", "created": [start, end], "l": 500, "o": ["-created"]},
                              headers={"x-api-key": self.api_key()}, timeout=60)
        r.raise_for_status()
        since_ms = int(since_utc.timestamp() * 1000)
        out = []
        for row in r.json().get("_rows", []):
            if row.get("status", True) is not False:
                continue
            created = str(row.get("created", ""))
            if created.isdigit() and int(created) < since_ms:
                continue
            out.append(RateFailure(key=str(row.get("key", "")), created=created,
                                   lender=str(row.get("lender", "")), description=str(row.get("description", ""))))
        return out

from datetime import datetime, timezone
from parser_bot.lf_api import LFClient, RateFailure

NS = "5716104026521600"


class FakeResp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status
    def json(self):
        return self._p
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Mimics the three LF calls: password-grant token, getCurrentUserAPIKey, lfiq execute/FindOp."""
    def __init__(self):
        self.calls = []
        self.token_calls = 0
    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(("POST", url, json, headers))
        if url.endswith("/token"):
            self.token_calls += 1
            return FakeResp({"access_token": f"tok{self.token_calls}", "refresh_token": "r", "expires_in": 1800})
        if url.endswith("/getCurrentUserAPIKey"):
            assert headers == {"Authorization": "Bearer tok1"}
            return FakeResp({"result": {"api_key": "KEY-1"}})
        if url.endswith("/execute/FindOp"):
            return FakeResp({"_rows": [
                {"key": "k1", "created": "1788472002780", "lender": "AAALendings", "description": "Can not parseAAALendingsNonQMAdjustmentPdfParser from x", "status": False},
                {"key": "k2", "created": "1788472002000", "lender": "Provident", "description": "Parsed 120 New Provident Rates", "status": True},
                {"key": "k3", "created": "1785766874168", "lender": "PennyMac", "description": "Can not parsePennyMacAdjustmentXlsxParser", "status": False},
                {"key": "k4", "created": "1788472001000", "lender": "Rocket", "description": "Can not parseRocketAdjustmentParser"},
            ], "l": 500, "_exact": False})
        raise AssertionError("unexpected url " + url)


def test_token_is_fetched_once_and_reused():
    s = FakeSession()
    clock = [1000.0]
    c = LFClient("https://lf", NS, "bot@lf", "pw", session=s, clock=lambda: clock[0])
    assert c.token() == "tok1"
    assert c.token() == "tok1"
    assert s.calls[0][:3] == ("POST", f"https://lf/api/oauth2/v1/{NS}/token",
                              {"grant_type": "password", "username": "bot@lf", "password": "pw"})
    clock[0] += 1800 - 200          # inside the 5-minute safety margin → refresh
    assert c.token() == "tok2"


def test_api_key_is_fetched_with_the_bearer_token_and_cached():
    s = FakeSession()
    c = LFClient("https://lf", NS, "u", "p", session=s, clock=lambda: 0.0)
    assert c.api_key() == "KEY-1"
    assert c.api_key() == "KEY-1"
    assert sum(1 for x in s.calls if x[1].endswith("/getCurrentUserAPIKey")) == 1
    assert s.calls[1][1] == f"https://lf/api/mobile/v1/{NS}/getCurrentUserAPIKey"


def test_failures_since_uses_findop_with_a_created_range_and_filters_client_side():
    s = FakeSession()
    c = LFClient("https://lf", NS, "u", "p", session=s, clock=lambda: 0.0)
    since = datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc)          # 1788429600000 ms
    out = c.failures_since(since)
    # k1 only: k2 status true, k3 older than `since`, k4 has no status (defaults to true)
    assert out == [RateFailure("k1", "1788472002780", "AAALendings", "Can not parseAAALendingsNonQMAdjustmentPdfParser from x")]
    method, url, body, headers = s.calls[-1]
    assert url == f"https://lf/api/lfiq/v1/{NS}/execute/FindOp"
    assert headers == {"x-api-key": "KEY-1"}
    assert body["kind"] == "RateUpdate" and body["o"] == ["-created"] and body["l"] == 500
    assert body["created"][0] <= "2026-09-02" and body["created"][1] >= "2026-09-04"   # wide day window around `since`


def test_created_at_parses_epoch_millis_and_iso():
    assert RateFailure("k", "1788472002780", "L", "d").created_at() == datetime(2026, 9, 3, 21, 46, 42, 780000, tzinfo=timezone.utc)
    assert RateFailure("k", "2026-09-03T14:10", "L", "d").created_at() == datetime(2026, 9, 3, 14, 10, tzinfo=timezone.utc)
    assert RateFailure("k", "", "L", "d").created_at() is None

from datetime import datetime, timezone
from parser_bot.lf_api import LFClient, RateFailure


class FakeResp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status
    def json(self):
        return self._p
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self):
        self.calls = []
        self.token_calls = 0
    def post(self, url, json=None, timeout=None):
        self.calls.append(("POST", url, json))
        self.token_calls += 1
        return FakeResp({"access_token": f"tok{self.token_calls}", "refresh_token": "r", "expires_in": 1800})
    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(("GET", url, params, headers))
        return FakeResp({"items": [
            {"key": "k1", "created": "2026-09-03T14:10", "lender": "AAALendings", "description": "Error while parsing rates for AAALendingsNonQM", "status": False},
            {"key": "k2", "created": "2026-09-03T14:05", "lender": "Provident", "description": "Parsed 120 New Provident Rates", "status": True},
            {"key": "k3", "created": "2026-09-03T14:00", "lender": "Rocket", "description": "Can not parseRocketAdjustmentParser"},
        ]})


def test_token_is_fetched_once_and_reused():
    s = FakeSession()
    clock = [1000.0]
    c = LFClient("https://lf", "LOAN_FACTORY", "bot@lf", "pw", session=s, clock=lambda: clock[0])
    assert c.token() == "tok1"
    assert c.token() == "tok1"
    assert s.calls[0] == ("POST", "https://lf/api/oauth2/v1/LOAN_FACTORY/token",
                          {"grant_type": "password", "username": "bot@lf", "password": "pw"})
    clock[0] += 1800 - 200          # inside the 5-minute safety margin → refresh
    assert c.token() == "tok2"


def test_failures_since_filters_status_false_only():
    s = FakeSession()
    c = LFClient("https://lf", "LOAN_FACTORY", "u", "p", session=s, clock=lambda: 0.0)
    out = c.failures_since(datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc))
    assert out == [RateFailure("k1", "2026-09-03T14:10", "AAALendings", "Error while parsing rates for AAALendingsNonQM")]
    method, url, params, headers = s.calls[-1]
    assert url == "https://lf/api/entity/v1/rate_update"
    assert params == {"created>": "2026-09-03T10:00", "l": "200", "o": "-created"}
    assert headers == {"Authorization": "Bearer tok1"}

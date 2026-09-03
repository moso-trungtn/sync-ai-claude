from parser_bot.jira import JiraClient
from parser_bot.state import NightState


class FakeResp:
    def __init__(self, payload, status=200): self._p, self.status_code = payload, status
    def json(self): return self._p
    def raise_for_status(self): pass


class FakeJira:
    def __init__(self):
        self.calls = []; self.auth = None; self.summary = "[Parser failed] 09/03/2026: AAA Lendings"
        self.transitions = [{"id": "841", "name": "Select for development"}]
    def post(self, url, json=None, timeout=None):
        self.calls.append(("POST", url, json))
        if url.endswith("/rest/api/2/issue"):
            return FakeResp({"key": "MOSO-9"})
        if url.endswith("/transitions"):
            self.transitions = [{"id": "4", "name": "Start Progress"}] if json["transition"]["id"] == "841" else []
            return FakeResp({})
        return FakeResp({})
    def get(self, url, params=None, timeout=None):
        self.calls.append(("GET", url, params))
        if url.endswith("/transitions"):
            return FakeResp({"transitions": self.transitions})
        return FakeResp({"fields": {"summary": self.summary}})
    def put(self, url, json=None, timeout=None):
        self.calls.append(("PUT", url, json)); self.summary = json["fields"]["summary"]; return FakeResp({}, 204)


def test_create_night_ticket_sets_fields_and_moves_to_in_progress():
    s = FakeJira()
    j = JiraClient("https://j", "me@x", "tok", "MOSO", "1:2", session=s)
    assert j.create_night_ticket("09/03/2026", ["AAA Lendings"]) == "MOSO-9"
    assert s.auth == ("me@x", "tok")
    create = s.calls[0][2]["fields"]
    assert create["summary"] == "[Parser failed] 09/03/2026: AAA Lendings"
    assert create["project"] == {"key": "MOSO"} and create["issuetype"] == {"name": "Task"}
    assert create["labels"] == ["parser"] and create["assignee"] == {"accountId": "1:2"}
    posted = [c for c in s.calls if c[0] == "POST" and c[1].endswith("/transitions")]
    assert [c[2]["transition"]["id"] for c in posted] == ["841", "4"]


def test_append_lender_and_ensure_ticket(tmp_path):
    s = FakeJira()
    j = JiraClient("https://j", "me@x", "tok", "MOSO", "1:2", session=s)
    j.append_lender("MOSO-9", "Rocket Pro")
    assert s.summary == "[Parser failed] 09/03/2026: AAA Lendings · Rocket Pro"
    j.append_lender("MOSO-9", "Rocket Pro")                       # idempotent
    assert s.summary.count("Rocket Pro") == 1
    j.append_lender("MOSO-9", "National Mortgage Service, Inc. (NMSI)")
    j.append_lender("MOSO-9", "National Mortgage Service, Inc. (NMSI)")  # idempotent with comma
    assert s.summary.count("National Mortgage Service, Inc. (NMSI)") == 1
    assert s.summary.endswith("Rocket Pro · National Mortgage Service, Inc. (NMSI)")
    st = NightState.load(str(tmp_path), "2026-09-03")
    assert j.ensure_ticket(st, "AAA Lendings", "09/03/2026") == "MOSO-9" and st.ticket == "MOSO-9"
    j.comment("MOSO-9", "hello")
    assert s.calls[-1] == ("POST", "https://j/rest/api/2/issue/MOSO-9/comment", {"body": "hello"})

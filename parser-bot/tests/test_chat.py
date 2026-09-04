from parser_bot.chat import ChatClient, CHAT_SCOPE


class FakeResp:
    status_code = 200
    def __init__(self, payload): self._p = payload
    def json(self): return self._p
    def raise_for_status(self): pass


class FakeSession:
    def __init__(self): self.calls = []
    def post(self, url, params=None, json=None, timeout=None):
        self.calls.append((url, params, json))
        return FakeResp({"name": "spaces/S/messages/M", "thread": {"name": "spaces/S/threads/T"}})


def test_post_with_thread_key_starts_or_joins_keyed_thread():
    s = FakeSession()
    c = ChatClient("/nonexistent/sa.json", "spaces/S", session=s)
    out = c.post("hello", thread_key="AAALendings-09-03")
    assert out["thread"]["name"] == "spaces/S/threads/T"
    url, params, body = s.calls[0]
    assert url == "https://chat.googleapis.com/v1/spaces/S/messages"
    assert params == {"messageReplyOption": "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"}
    assert body == {"text": "hello", "thread": {"threadKey": "AAALendings-09-03"}}


def test_post_with_thread_name_replies_in_existing_thread():
    s = FakeSession()
    ChatClient("/nonexistent/sa.json", "spaces/S", session=s).post("hi", thread_name="spaces/S/threads/T")
    assert s.calls[0][2] == {"text": "hi", "thread": {"name": "spaces/S/threads/T"}}
    assert CHAT_SCOPE == "https://www.googleapis.com/auth/chat.bot"


def test_bare_post_omits_reply_option():
    s = FakeSession()
    ChatClient("/nonexistent/sa.json", "spaces/S", session=s).post("plain")
    url, params, body = s.calls[0]
    assert params is None or params == {}
    assert body == {"text": "plain"}

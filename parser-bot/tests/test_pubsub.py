from parser_bot.pubsub import PubSubPuller


class Msg:
    def __init__(self, ack_id, data): self.ack_id, self.message = ack_id, type("M", (), {"data": data})()


class Resp:
    def __init__(self, msgs): self.received_messages = msgs


class FakeClient:
    def __init__(self, msgs): self.msgs, self.pulls, self.acked, self.closed = msgs, [], [], False
    def pull(self, request=None, timeout=None): self.pulls.append((request, timeout)); return Resp(self.msgs)
    def acknowledge(self, request=None): self.acked.append(request["ack_ids"])
    def close(self): self.closed = True


def make(msgs):
    p = PubSubPuller("projects/p/subscriptions/s", "/nope/sa.json")
    p._client = FakeClient(msgs)
    return p


def test_pull_decodes_json_and_acks_every_pulled_message():
    p = make([Msg("a1", b'{"type": "MESSAGE"}'), Msg("a2", b"not json"), Msg("a3", b'{"chat": {}}')])
    events = p.pull()
    assert events == [{"type": "MESSAGE"}, {"chat": {}}]
    assert p._client.acked == [["a1", "a2", "a3"]]        # the poison message is acked, not redelivered


def test_pull_reuses_one_client_and_close_drops_it():
    p = make([])
    client = p.client
    p.pull(); p.pull()
    assert p.client is client and len(client.pulls) == 2
    assert client.pulls[0][0]["subscription"] == "projects/p/subscriptions/s"
    p.close()
    assert client.closed is True and p._client is None

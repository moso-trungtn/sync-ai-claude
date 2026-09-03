"""Synchronous Pub/Sub pull for the Chat app subscription. Decodes JSON and acks what it returns."""
from __future__ import annotations

import json


def pull_events(subscription: str, sa_file: str, max_messages: int = 10, timeout: float = 30) -> list[dict]:
    from google.cloud import pubsub_v1
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_file(sa_file)
    client = pubsub_v1.SubscriberClient(credentials=creds)
    resp = client.pull(request={"subscription": subscription, "max_messages": max_messages}, timeout=timeout)
    events, ack_ids = [], []
    for rm in resp.received_messages:
        ack_ids.append(rm.ack_id)
        try:
            events.append(json.loads(rm.message.data.decode("utf-8")))
        except (ValueError, UnicodeDecodeError):
            continue
    if ack_ids:
        client.acknowledge(request={"subscription": subscription, "ack_ids": ack_ids})
    return events

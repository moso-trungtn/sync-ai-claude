"""Synchronous Pub/Sub pull for the Chat app subscription.

A pull ACKS EVERY MESSAGE IT PULLED — including payloads that fail JSON decode. Those are
dropped on purpose: an unacked poison message would be redelivered forever and would block
every real command behind it.
"""
from __future__ import annotations

import json
import threading


class PubSubPuller:
    """One SubscriberClient per (subscription, service account), built on first pull and kept."""

    def __init__(self, subscription: str, sa_file: str):
        self.subscription = subscription
        self.sa_file = sa_file
        self._client = None
        self._lock = threading.Lock()

    @property
    def client(self):
        if self._client is None:
            with self._lock:
                if self._client is None:
                    from google.cloud import pubsub_v1
                    from google.oauth2 import service_account
                    creds = service_account.Credentials.from_service_account_file(self.sa_file)
                    self._client = pubsub_v1.SubscriberClient(credentials=creds)
        return self._client

    def pull(self, max_messages: int = 10, timeout: float = 30) -> list[dict]:
        """Return the decoded events and ack everything pulled, decodable or not (see module docstring)."""
        client = self.client
        resp = client.pull(request={"subscription": self.subscription, "max_messages": max_messages}, timeout=timeout)
        events, ack_ids = [], []
        for rm in resp.received_messages:
            ack_ids.append(rm.ack_id)
            try:
                events.append(json.loads(rm.message.data.decode("utf-8")))
            except (ValueError, UnicodeDecodeError):
                continue
        if ack_ids:
            client.acknowledge(request={"subscription": self.subscription, "ack_ids": ack_ids})
        return events

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


_PULLERS: dict[tuple[str, str], PubSubPuller] = {}
_PULLERS_LOCK = threading.Lock()


def pull_events(subscription: str, sa_file: str, max_messages: int = 10, timeout: float = 30) -> list[dict]:
    """Thin compatibility wrapper: one cached PubSubPuller per (subscription, service account)."""
    key = (subscription, sa_file)
    with _PULLERS_LOCK:
        puller = _PULLERS.get(key)
        if puller is None:
            puller = _PULLERS[key] = PubSubPuller(subscription, sa_file)
    return puller.pull(max_messages=max_messages, timeout=timeout)

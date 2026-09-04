"""Post messages into the Chat space as the app (service account, chat.bot scope)."""
from __future__ import annotations

import threading

CHAT_SCOPE = "https://www.googleapis.com/auth/chat.bot"
API = "https://chat.googleapis.com/v1"


class ChatClient:
    def __init__(self, sa_file: str, space: str, session=None):
        self.sa_file = sa_file
        self.space = space
        self._session = session
        self._lock = threading.Lock()

    @property
    def session(self):
        if self._session is None:
            with self._lock:
                if self._session is None:
                    from google.oauth2 import service_account
                    from google.auth.transport.requests import AuthorizedSession
                    creds = service_account.Credentials.from_service_account_file(self.sa_file, scopes=[CHAT_SCOPE])
                    self._session = AuthorizedSession(creds)
        return self._session

    def post(self, text: str, thread_key: str | None = None, thread_name: str | None = None) -> dict:
        body: dict = {"text": text}
        if thread_name:
            body["thread"] = {"name": thread_name}
        elif thread_key:
            body["thread"] = {"threadKey": thread_key}
        # Chat rejects messageReplyOption on a message that names no thread (400 "does not specify which
        # message to reply to"), so only send it when a thread key/name is present.
        params = {"messageReplyOption": "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"} if "thread" in body else None
        r = self.session.post(f"{API}/{self.space}/messages", params=params, json=body, timeout=30)
        r.raise_for_status()
        return r.json()

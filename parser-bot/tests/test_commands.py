import json
from parser_bot.commands import parse_event, Command


def classic(text, argument=None, etype="MESSAGE"):
    msg = {"text": text, "sender": {"name": "users/1", "displayName": "Trung", "email": "t@lf.com", "type": "HUMAN"},
           "thread": {"name": "spaces/S/threads/T"}}
    if argument is not None:
        msg["argumentText"] = argument
    return {"type": etype, "eventTime": "2026-09-03T14:20:00Z", "space": {"name": "spaces/S"}, "message": msg}


def test_fix_command_from_classic_event_uses_argument_text():
    cmd = parse_event(classic("@Parser Bot fix AAA", argument=" fix AAA"))
    assert cmd == Command("fix", "AAA", "t@lf.com", "Trung", "spaces/S/threads/T", "spaces/S")


def test_variants_and_non_commands():
    assert parse_event(classic("@Parser Bot fix all")).kind == "fix_all"
    assert parse_event(classic("@Parser Bot  SKIP Provident")).lender_text == "Provident"
    assert parse_event(classic("@Parser Bot retry rocket")).kind == "retry"
    assert parse_event(classic("@Parser Bot status")).kind == "status"
    assert parse_event(classic("@Parser Bot hello there")) is None
    assert parse_event(classic("fix AAA", etype="ADDED_TO_SPACE")) is None
    assert parse_event({"type": "MESSAGE", "space": {"name": "spaces/S"},
                        "message": {"text": "fix AAA", "sender": {"type": "BOT", "email": "", "displayName": "b"}, "thread": {"name": "x"}}}) is None


def test_new_payload_shape_is_supported():
    ev = {"chat": {"messagePayload": {"space": {"name": "spaces/S"},
                                      "message": {"text": "@Parser Bot fix AAA Lendings", "argumentText": " fix AAA Lendings",
                                                  "sender": {"email": "a@lf.com", "displayName": "A", "type": "HUMAN"},
                                                  "thread": {"name": "spaces/S/threads/Z"}}}}}
    cmd = parse_event(ev)
    assert cmd.kind == "fix" and cmd.lender_text == "AAA Lendings" and cmd.thread_name == "spaces/S/threads/Z"

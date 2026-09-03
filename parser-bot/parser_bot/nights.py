"""Pure time helpers. A "night" is the ICT evening date; 00:00-11:59 ICT belongs to the previous date."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

ICT = ZoneInfo("Asia/Ho_Chi_Minh")
PT = ZoneInfo("US/Pacific")


def _hm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def night_id(now: datetime) -> str:
    local = now.astimezone(ICT)
    if local.hour < 12:
        local = local - timedelta(days=1)
    return local.date().isoformat()


def in_window(now: datetime, start: str, end: str) -> bool:
    t = now.astimezone(ICT).time().replace(second=0, microsecond=0)
    s, e = _hm(start), _hm(end)
    if s <= e:
        return s <= t < e
    return t >= s or t < e


def pacific_date(now: datetime) -> str:
    return now.astimezone(PT).strftime("%m/%d/%Y")


def ict_clock(now: datetime) -> str:
    return now.astimezone(ICT).strftime("%H:%M ICT")

from datetime import datetime, timezone
from parser_bot.nights import ICT, night_id, in_window, pacific_date, ict_clock


def ict(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=ICT)


def test_night_id_groups_evening_and_next_morning():
    assert night_id(ict(2026, 9, 3, 21)) == "2026-09-03"
    assert night_id(ict(2026, 9, 4, 3)) == "2026-09-03"
    assert night_id(ict(2026, 9, 4, 12)) == "2026-09-04"


def test_in_window_handles_overnight_range():
    assert in_window(ict(2026, 9, 3, 19, 30), "19:30", "05:30") is True
    assert in_window(ict(2026, 9, 3, 23), "19:30", "05:30") is True
    assert in_window(ict(2026, 9, 4, 3), "19:30", "05:30") is True
    assert in_window(ict(2026, 9, 4, 5, 30), "19:30", "05:30") is False
    assert in_window(ict(2026, 9, 3, 12), "19:30", "05:30") is False


def test_pacific_date_and_clock():
    # 21:00 ICT on 09/03 is 07:00 PDT on 09/03
    assert pacific_date(ict(2026, 9, 3, 21)) == "09/03/2026"
    # 03:00 ICT on 09/04 is 13:00 PDT on 09/03
    assert pacific_date(ict(2026, 9, 4, 3)) == "09/03/2026"
    assert ict_clock(datetime(2026, 9, 3, 14, 14, tzinfo=timezone.utc)) == "21:14 ICT"

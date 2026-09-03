from parser_bot.state import NightState, LenderState, TRIAGED


def test_state_roundtrip_and_seen_keys(tmp_path):
    st = NightState.load(str(tmp_path), "2026-09-03")
    assert st.lenders == {} and st.ticket is None and st.prepared is False
    assert st.mark_seen("k1") is True
    assert st.mark_seen("k1") is False
    st.lenders[st.key("AAALendings", "QM")] = LenderState(
        lender="AAALendings", channel="QM", status=TRIAGED, detected_at="2026-09-03T21:14+07:00",
        cause="CRAWL_MISMATCH", thread_name="spaces/x/threads/y")
    st.ticket = "MOSO-1"
    st.prepared = True
    st.save()

    again = NightState.load(str(tmp_path), "2026-09-03")
    assert again.mark_seen("k1") is False
    assert again.ticket == "MOSO-1" and again.prepared is True
    ls = again.lenders["AAALendings|QM"]
    assert ls.status == TRIAGED and ls.thread_name == "spaces/x/threads/y"
    assert (tmp_path / "2026-09-03.json").exists()

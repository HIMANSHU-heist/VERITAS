import pandas as pd
import pytest
from python.dataclock import DataClock, LeakageError

AS_OF = "2024-03-12 03:00:00+00:00"   # 08:30 IST


@pytest.fixture(scope="module")
def dc():
    return DataClock(["NIFTY", "NIKKEI", "SP500"])


def test_no_future_rows_visible(dc):
    for name in dc.frames:
        df = dc.get(name, AS_OF)
        assert (df["available_at"] <= pd.Timestamp(AS_OF)).all()


def test_last_visible_dates(dc):
    for name in ["NIFTY", "NIKKEI", "SP500"]:
        last = dc.get(name, AS_OF)["date"].iloc[-1]
        assert str(last.date()) == "2024-03-11"


def test_indian_bar_appears_after_close(dc):
    # After 10:15 UTC on 12 Mar, the NIFTY bar for 12 Mar becomes visible
    last = dc.get("NIFTY", "2024-03-12 10:30:00+00:00")["date"].iloc[-1]
    assert str(last.date()) == "2024-03-12"


def test_tripwire_blocks_future_dates(dc):
    with pytest.raises(LeakageError):
        dc.check_text("Nifty closed strongly on 2024-03-14", AS_OF)


def test_tripwire_allows_past_dates(dc):
    assert dc.check_text("Nifty closed on 2024-03-11", AS_OF)


def test_audit_log_records_requests(dc):
    n = len(dc.log)
    dc.get("NIFTY", AS_OF)
    assert len(dc.log) == n + 1
    assert dc.log[-1]["rows_hidden_future"] > 0

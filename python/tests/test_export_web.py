from python.export_web import build


def test_export_contract():
    d = build()
    n = len(d["cards"])
    assert n == d["summary"]["n_days"]
    for k in ("ml_gates", "pipeline", "buy_hold"):
        assert len(d["series"][k]) == n
    assert abs(d["series"]["pipeline"][-1] - d["summary"]["pipeline"]["net_pnl"]) < 1.0
    assert abs(d["series"]["ml_gates"][-1] - d["summary"]["ml_gates"]["net_pnl"]) < 1.0


def test_buy_hold_series_matches_scoreboard():
    d = build()
    assert abs(d["series"]["buy_hold"][-1] - d["summary"]["buy_hold"]["net_pnl"]) < 1.0

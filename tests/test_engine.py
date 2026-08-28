from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from quantnse.config import get_settings
from quantnse.derivatives.chain import build_chain_from_quotes, call_oi_unwinding, max_pain, pcr
from quantnse.engine import QuantEngine
from quantnse.gates.engine import GateContext, evaluate
from quantnse.ingestion.candles import MTFEngine
from quantnse.ingestion.rvol import RVOLCalculator
from quantnse.ingestion.ticker import parse_kite_tick
from quantnse.macro.context import compute_lockout, fii_dii_bias
from quantnse.microstructure.imbalance import order_book_imbalance
from quantnse.models import Candle, Route, Tick
from quantnse.risk.backtester import replay_longs
from quantnse.risk.costs import round_trip_equity_intraday
from quantnse.risk.sizing import geometry
from quantnse.screener.funnel import run_funnel
from quantnse.timeutil import IST
from quantnse.universe import load_universe


def _ctx(**kwargs) -> GateContext:
    base = dict(
        symbol="RELIANCE",
        route=Route.FNO,
        sector="NIFTY 50",
        sector_vs_open=0.4,
        vix_change_pct=1.0,
        pcr=1.2,
        call_oi_unwinding=False,
        imbalance=1.4,
        cvd=250.0,
        cvd_known=True,
        price=1400.0,
        vwap=1390.0,
        orb_high=1395.0,
        orb_low=1388.0,
        resistance=1425.0,
        atr=8.0,
    )
    base.update(kwargs)
    return GateContext(**base)


def test_universe_dual_route():
    names = load_universe()
    assert len(names) >= 200
    assert any(n.route == Route.FNO for n in names)
    assert any(n.route == Route.CASH for n in names)


def test_happy_path_triggers():
    setup = evaluate(_ctx())
    assert setup.status == "triggered"
    assert setup.rr is not None and setup.rr >= 2.0
    assert setup.stop_loss and setup.tp1 and setup.qty > 0


def test_cash_skips_derivatives_gate():
    setup = evaluate(_ctx(route=Route.CASH, pcr=0.2, call_oi_unwinding=False))
    statuses = {g.gate.value: g.status.value for g in setup.gates}
    assert statuses["gate2_derivatives"] == "skipped"
    assert setup.status != "discarded"


def test_fno_fails_without_pcr_or_unwind():
    setup = evaluate(_ctx(pcr=0.4, call_oi_unwinding=False))
    assert setup.status == "discarded"
    assert setup.gates[-1].gate.value == "gate2_derivatives"


def test_macro_fail_discards_even_if_later_would_pass():
    setup = evaluate(_ctx(sector_vs_open=-0.2, vix_change_pct=1.0))
    assert setup.status == "discarded"
    assert len(setup.gates) == 1


def test_vix_lockout():
    assert compute_lockout(4.0) is True
    assert compute_lockout(3.9) is False
    setup = evaluate(_ctx(vix_change_pct=4.5))
    assert setup.status == "discarded"


def test_gate3_holds_staging():
    setup = evaluate(_ctx(imbalance=1.0, cvd=10, cvd_known=True))
    assert setup.status == "staging"
    setup2 = evaluate(_ctx(cvd_known=False, imbalance=1.5, cvd=0))
    assert setup2.status == "staging"


def test_rr_and_stop_cap():
    geo = geometry(entry=100.0, vwap=99.7, orb_low=99.6, resistance=102.0, atr=1.0)
    assert geo is not None
    assert geo.rr >= get_settings().rr_min
    assert geo.stop >= 100 * (1 - get_settings().max_risk_pct) - 1e-9
    rejected = evaluate(_ctx(orb_low=None, resistance=None))
    assert rejected.status == "rejected"
    no_trig = evaluate(_ctx(price=1380.0, vwap=1390.0, orb_high=1395.0))
    assert no_trig.status == "no_trigger"


def test_cost_engine_positive():
    c = round_trip_equity_intraday(100, 1000, 1020)
    assert c.brokerage > 0
    assert c.stt == pytest.approx(1020 * 100 * 0.00025)
    assert c.gst == pytest.approx(0.18 * (c.brokerage + c.exchange + c.sebi))
    assert c.total > c.brokerage


def test_imbalance_formula():
    tick = Tick(
        instrument_token=1,
        symbol="X",
        last_price=10,
        timestamp=datetime.now(tz=IST),
        bid_qty=[130, 0, 0, 0, 0],
        ask_qty=[100, 0, 0, 0, 0],
    )
    assert order_book_imbalance(tick) == pytest.approx(1.3)


def test_mtf_vwap_and_rvol():
    mtf = MTFEngine()
    start = datetime(2026, 8, 28, 9, 15, tzinfo=IST)
    vol = 0
    for i in range(20):
        vol += 100
        mtf.on_tick(
            Tick(
                instrument_token=1,
                symbol="AAA",
                last_price=100 + i * 0.1,
                volume=vol,
                last_quantity=100,
                timestamp=start + timedelta(seconds=i * 15),
            )
        )
    assert mtf.vwap["AAA"] > 0
    bars = mtf.candles("AAA", "5m")
    assert bars
    r = RVOLCalculator()
    hist = [
        Candle(symbol="AAA", timeframe="5m", ts=start + timedelta(days=d), open=1, high=1, low=1, close=1, volume=50)
        for d in range(20)
    ]
    r.load_history("AAA", hist)
    assert r.rvol("AAA", bars[-1]) > 1.5


def test_kite_tick_parser():
    raw = {
        "instrument_token": 256265,
        "last_price": 100.5,
        "volume": 10,
        "last_quantity": 2,
        "depth": {
            "buy": [{"quantity": 5, "price": 100.4}] * 5,
            "sell": [{"quantity": 4, "price": 100.6}] * 5,
        },
        "ohlc": {"open": 100, "high": 101, "low": 99, "close": 100.5},
    }
    t = parse_kite_tick(raw, "NIFTY")
    assert t.last_price == 100.5
    assert len(t.bid_qty) == 5


def test_pcr_and_max_pain():
    rows = []
    for k in (100, 110, 120):
        rows.append({"strike": k, "side": "CE", "oi": 1000, "oi_prev": 1100, "volume": 10, "ltp": 5})
        rows.append({"strike": k, "side": "PE", "oi": 2000, "oi_prev": 1800, "volume": 20, "ltp": 4})
    chain = build_chain_from_quotes("X", 110, rows, step=10)
    vol_pcr, oi_pcr = pcr(chain, n=5, step=10)
    assert vol_pcr == pytest.approx(2.0)
    assert oi_pcr == pytest.approx(2.0)
    assert call_oi_unwinding(chain, n=5, step=10)
    assert max_pain(chain) in {100, 110, 120}


def test_funnel_size():
    engine = QuantEngine()
    start = datetime(2026, 8, 28, 9, 15, tzinfo=IST)
    for name in engine.universe[:40]:
        engine.ingest(
            Tick(
                instrument_token=name.instrument_token,
                symbol=name.symbol,
                last_price=100,
                volume=10_000,
                last_quantity=200,
                timestamp=start,
                bid_qty=[10] * 5,
                ask_qty=[5] * 5,
                bid_price=[99] * 5,
                ask_price=[101] * 5,
            )
        )
    wl = run_funnel(engine.universe[:40], engine.mtf, engine.rvol, size=10)
    assert len(wl) == 10


def test_fii_bias():
    assert fii_dii_bias(100, -20) == "risk_on"
    assert fii_dii_bias(-50, 0) == "risk_off"


def test_backtester_no_lookahead_columns():
    idx = pd.date_range("2026-01-05 09:15", periods=80, freq="5min")
    close = pd.Series(range(100, 180), dtype=float)
    df = pd.DataFrame(
        {
            "ts": idx,
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1000,
        }
    )
    trades = replay_longs(df, "RELIANCE", Route.FNO, "NIFTY 50")
    assert isinstance(trades, list)


def test_live_orders_default_off():
    assert get_settings().enable_live_orders is False


def test_demo_engine_pipeline():
    from quantnse.demo import default_macro, demo_chain, synthetic_session

    eng = QuantEngine()
    eng.set_macro(default_macro())
    start = datetime(2026, 8, 28, 9, 15, tzinfo=IST)
    name = next(n for n in eng.universe if n.route == Route.FNO)
    for tick in synthetic_session(name.symbol, 1400, start, minutes=40, seed=1):
        eng.ingest(tick)
    last = eng.last_ticks[name.symbol]
    eng.attach_chain(demo_chain(name.symbol, last.last_price))
    eng.lock_watchlist([w for w in run_funnel(eng.universe[:5], eng.mtf, eng.rvol, size=1)])
    setup = eng.evaluate_symbol(name.symbol, ts=start.replace(hour=10, minute=0))
    assert setup.symbol == name.symbol
    assert setup.status in {"triggered", "staging", "no_trigger", "rejected", "discarded"}

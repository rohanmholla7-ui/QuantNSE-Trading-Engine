from __future__ import annotations

import asyncio
from typing import Any

from quantnse.config import get_settings
from quantnse.engine import QuantEngine
from quantnse.ingestion.auth import make_kite
from quantnse.ingestion.ticker import parse_kite_tick
from quantnse.universe import load_universe


def _token_map(kite: Any, symbols: list[str]) -> dict[int, str]:
    instruments = kite.instruments("NSE")
    wanted = set(symbols)
    out: dict[int, str] = {}
    for row in instruments:
        if row.get("tradingsymbol") in wanted and row.get("segment") == "NSE":
            out[int(row["instrument_token"])] = row["tradingsymbol"]
    return out


def run_kite_ticker(engine: QuantEngine, tokens: list[int], token_to_symbol: dict[int, str]) -> None:
    from kiteconnect import KiteTicker

    settings = get_settings()
    ticker = KiteTicker(settings.kite_api_key, settings.kite_access_token)

    def on_ticks(_ws: Any, ticks: list[dict]) -> None:
        for raw in ticks:
            symbol = token_to_symbol.get(int(raw.get("instrument_token") or 0))
            if not symbol:
                continue
            engine.ingest(parse_kite_tick(raw, symbol))

    def on_connect(ws: Any, _payload: Any) -> None:
        ws.subscribe(tokens)
        ws.set_mode(ws.MODE_FULL, tokens)

    ticker.on_ticks = on_ticks
    ticker.on_connect = on_connect
    ticker.connect(threaded=True)


def demo_loop(engine: QuantEngine) -> None:
    from quantnse.demo import default_macro, demo_chain, synthetic_session
    from quantnse.timeutil import now_ist

    engine.set_macro(default_macro())
    names = list(engine.universe)
    start = now_ist().replace(hour=9, minute=15, second=0, microsecond=0)
    for i, name in enumerate(names):
        base = 100 + i * 17
        for tick in synthetic_session(name.symbol, base, start, minutes=20, seed=i):
            engine.ingest(tick)
        last = engine.last_ticks[name.symbol]
        engine.attach_chain(demo_chain(name.symbol, last.last_price))
    engine.lock_watchlist()
    engine.evaluate_watchlist()
    from datetime import timedelta

    from quantnse.risk.tracker import net_from_gross, sim_qty

    now = now_ist()
    if not engine.tracker.history():
        samples = [
            ("HDFCBANK", "NIFTY BANK", 1650.0, "WIN", 0),
            ("ITC", "NIFTY FMCG", 412.0, "LOSS", 0),
            ("VEDL", "NIFTY METAL", 448.0, "WIN", 5),
            ("DIXON", "NIFTY 500", 15200.0, "SQUARED_OFF", 8),
        ]
        for i, (sym, sector, entry, outcome, days_ago) in enumerate(samples):
            qty = sim_qty(entry)
            if outcome == "WIN":
                exit_px = entry * 1.016
            elif outcome == "LOSS":
                exit_px = entry * 0.992
            else:
                exit_px = entry * 1.002
            gross = qty * (exit_px - entry)
            engine.tracker.seed(
                {
                    "ts": (now - timedelta(days=days_ago)).replace(hour=10, minute=5),
                    "symbol": sym,
                    "sector": sector,
                    "entry": entry,
                    "target": entry * 1.016,
                    "sl": entry * 0.992,
                    "exit": exit_px,
                    "qty": qty,
                    "notional": qty * entry,
                    "gross_pnl": gross,
                    "net_pnl": net_from_gross(gross, qty, entry),
                    "outcome": outcome,
                }
            )
    try:
        from quantnse.ingestion.duck import CandleStore

        CandleStore().persist_engine(engine.mtf)
    except Exception:
        pass


def main_live() -> None:
    settings = get_settings()
    engine = QuantEngine()
    kite = make_kite()
    universe = load_universe()
    symbols = [n.symbol for n in universe]
    mapping = _token_map(kite, symbols)
    tokens = list(mapping.keys())
    run_kite_ticker(engine, tokens, mapping)
    print("Kite ticker running. Ctrl+C to stop.")
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        return

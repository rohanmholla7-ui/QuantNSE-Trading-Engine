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
    names = engine.universe[: engine.settings.watchlist_size]
    start = now_ist().replace(hour=9, minute=15, second=0, microsecond=0)
    for i, name in enumerate(names):
        base = 100 + i * 17
        for tick in synthetic_session(name.symbol, base, start, minutes=20, seed=i):
            engine.ingest(tick)
        last = engine.last_ticks[name.symbol]
        engine.attach_chain(demo_chain(name.symbol, last.last_price))
    engine.lock_watchlist()
    engine.evaluate_watchlist()
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
    tokens = list(mapping.keys())[: min(len(symbols), 200)]
    run_kite_ticker(engine, tokens, mapping)
    print("Kite ticker running. Ctrl+C to stop.")
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        return

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from quantnse.config import get_settings
from quantnse.derivatives.chain import (
    ChainSnapshot,
    call_oi_unwinding,
    nearest_call_oi_wall,
    pcr,
)
from quantnse.gates.engine import GateContext, evaluate
from quantnse.ingestion.candles import MTFEngine
from quantnse.ingestion.rvol import RVOLCalculator
from quantnse.macro.context import compute_lockout, snapshot_from_state
from quantnse.microstructure.cvd import CVDTracker
from quantnse.microstructure.imbalance import order_book_imbalance
from quantnse.models import MacroSnapshot, Route, Setup, Tick, UniverseName, WatchlistItem
from quantnse.screener.funnel import run_funnel
from quantnse.store import StateStore
from quantnse.timeutil import now_ist, past_square_off
from quantnse.universe import by_symbol, load_universe


def token_for(symbol: str) -> int:
    return int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16)


class QuantEngine:
    def __init__(self, store: StateStore | None = None) -> None:
        self.settings = get_settings()
        self.store = store or StateStore(self.settings.redis_url)
        self.mtf = MTFEngine()
        self.rvol = RVOLCalculator()
        self.cvd = CVDTracker()
        self.universe = load_universe()
        self.lookup = by_symbol(self.universe)
        self.watchlist: list[WatchlistItem] = []
        self.last_ticks: dict[str, Tick] = {}
        self.chains: dict[str, ChainSnapshot] = {}
        self.prev_close: dict[str, float] = {}
        self.setups: dict[str, Setup] = {}
        self.square_off_alerts: list[dict[str, Any]] = []
        self.news_breaker = False
        self.funnel_locked = False
        for name in self.universe:
            if not name.instrument_token:
                name.instrument_token = token_for(name.symbol)

    def set_macro(self, snap: MacroSnapshot) -> None:
        self.store.set_json("macro", snap.model_dump())

    def macro(self) -> MacroSnapshot:
        snap = snapshot_from_state(self.store)
        snap.news_breaker = self.news_breaker or snap.news_breaker
        snap.vix_lockout = compute_lockout(snap.vix_change_pct, snap.news_breaker)
        return snap

    def ingest(self, tick: Tick) -> None:
        self.last_ticks[tick.symbol] = tick
        self.mtf.on_tick(tick)
        self.cvd.on_tick(tick)
        self.store.set_json(f"tick:{tick.symbol}", tick.model_dump())
        if past_square_off(tick.timestamp):
            self._square_off(tick.symbol)

    def lock_watchlist(self, items: list[WatchlistItem] | None = None) -> list[WatchlistItem]:
        if items is None:
            items = run_funnel(self.universe, self.mtf, self.rvol, self.prev_close)
        self.watchlist = items
        self.funnel_locked = True
        self.store.set_json("watchlist", [w.model_dump() for w in items])
        return items

    def watch_symbols(self) -> list[str]:
        if self.watchlist:
            return [w.symbol for w in self.watchlist]
        return [n.symbol for n in self.universe]

    def attach_chain(self, chain: ChainSnapshot) -> None:
        self.chains[chain.symbol] = chain

    def evaluate_symbol(self, symbol: str, ts: datetime | None = None) -> Setup:
        name = self.lookup.get(symbol) or UniverseName(symbol=symbol)
        tick = self.last_ticks.get(symbol)
        price = tick.last_price if tick else (self.mtf.last_close(symbol) or 0.0)
        vwap = self.mtf.vwap.get(symbol, price)
        session = ts or now_ist()
        orb_h, orb_l = self.mtf.orb_15m(symbol, session)
        bars = self.mtf.candles(symbol, "5m", 20)
        atr = 0.0
        if len(bars) >= 5:
            ranges = [c.high - c.low for c in bars[-14:]]
            atr = sum(ranges) / len(ranges)
        else:
            atr = price * 0.01
        macro = self.macro()
        sector_vs = macro.sector_vs_open.get(name.sector, macro.sector_vs_open.get("NIFTY 50", 0.1))
        chain = self.chains.get(symbol)
        vol_pcr = oi_pcr = None
        unwind = False
        resistance = price * 1.016
        if chain:
            vol_pcr, oi_pcr = pcr(chain)
            unwind = call_oi_unwinding(chain)
            wall = nearest_call_oi_wall(chain, price)
            if wall:
                resistance = wall
        pcr_val = oi_pcr if oi_pcr is not None else vol_pcr
        imb = order_book_imbalance(tick) if tick else None
        known = bool(tick and self.cvd.classified(tick))
        ctx = GateContext(
            symbol=symbol,
            route=name.route,
            sector=name.sector,
            sector_vs_open=sector_vs,
            vix_change_pct=macro.vix_change_pct,
            pcr=pcr_val,
            call_oi_unwinding=unwind,
            imbalance=imb,
            cvd=self.cvd.value(symbol),
            cvd_known=known,
            price=price,
            vwap=vwap,
            orb_high=orb_h,
            orb_low=orb_l,
            resistance=resistance,
            atr=atr,
            news_breaker=macro.news_breaker,
        )
        setup = evaluate(ctx, ts=session)
        self.setups[symbol] = setup
        return setup

    def evaluate_watchlist(self) -> list[Setup]:
        out = [self.evaluate_symbol(s) for s in self.watch_symbols()]
        self.store.set_json("setups", [s.model_dump() for s in out])
        triggered = [s for s in out if s.status == "triggered"]
        self.store.set_json("alerts", [s.model_dump() for s in triggered])
        return out

    def _square_off(self, symbol: str) -> None:
        alert = {
            "symbol": symbol,
            "reason": "Mandatory 15:18 IST time exit",
            "ts": now_ist().isoformat(),
            "live_order": False,
        }
        if self.settings.enable_live_orders:
            alert["live_order"] = self._place_live_exit(symbol)
        self.square_off_alerts.append(alert)
        self.store.set_json("square_off", self.square_off_alerts[-50:])

    def _place_live_exit(self, symbol: str) -> dict[str, Any]:
        if not self.settings.enable_live_orders:
            return {"placed": False, "reason": "ENABLE_LIVE_ORDERS=false"}
        try:
            from quantnse.ingestion.auth import make_kite

            kite = make_kite()
            return {"placed": True, "order": kite.place_order(
                variety="regular",
                exchange="NSE",
                tradingsymbol=symbol,
                transaction_type="SELL",
                quantity=1,
                product="MIS",
                order_type="MARKET",
            )}
        except Exception as exc:
            return {"placed": False, "reason": str(exc)}

    def dashboard_state(self) -> dict[str, Any]:
        macro = self.macro()
        return {
            "mode": self.settings.quantnse_mode,
            "using_redis": self.store.using_redis,
            "live_orders": self.settings.enable_live_orders,
            "watchlist": [w.model_dump() for w in self.watchlist],
            "setups": [s.model_dump() for s in self.setups.values()],
            "macro": macro.model_dump(),
            "square_off": self.square_off_alerts[-20:],
            "vwap": self.mtf.vwap,
            "disclaimer": (
                "QuantNSE is a personal analytical decision-support tool, not investment advice. "
                "Not a SEBI-registered Research Analyst product. Markets involve risk."
            ),
        }

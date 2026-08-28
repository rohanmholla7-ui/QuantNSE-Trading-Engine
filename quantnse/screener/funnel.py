from __future__ import annotations

from quantnse.config import get_settings
from quantnse.ingestion.candles import MTFEngine
from quantnse.ingestion.rvol import RVOLCalculator
from quantnse.models import Route, UniverseName, WatchlistItem


def _gap_pct(engine: MTFEngine, symbol: str, prev_close: float | None) -> float:
    last = engine.last_close(symbol)
    if last is None or not prev_close:
        return 0.0
    return (last - prev_close) / prev_close * 100.0


def score_name(
    name: UniverseName,
    engine: MTFEngine,
    rvol: RVOLCalculator,
    prev_close: dict[str, float],
) -> WatchlistItem:
    bars5 = engine.candles(name.symbol, "5m", 1)
    rv = rvol.rvol(name.symbol, bars5[-1] if bars5 else None)
    gap = abs(_gap_pct(engine, name.symbol, prev_close.get(name.symbol)))
    last = engine.last_close(name.symbol) or 0.0
    day_range = 0.0
    ohlc_bars = engine.candles(name.symbol, "1m", 120)
    if ohlc_bars:
        hi = max(c.high for c in ohlc_bars)
        lo = min(c.low for c in ohlc_bars)
        if last:
            day_range = (hi - lo) / last * 100.0
    score = rv * 2.0 + gap + day_range
    return WatchlistItem(
        symbol=name.symbol,
        score=score,
        rvol=rv,
        gap_pct=gap,
        route=name.route,
        instrument_token=name.instrument_token,
        sector=name.sector,
    )


def run_funnel(
    universe: list[UniverseName],
    engine: MTFEngine,
    rvol: RVOLCalculator,
    prev_close: dict[str, float] | None = None,
    size: int | None = None,
) -> list[WatchlistItem]:
    settings = get_settings()
    n = size or settings.watchlist_size
    prev_close = prev_close or {}
    ranked = [score_name(u, engine, rvol, prev_close) for u in universe]
    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked[:n]


def split_routes(watchlist: list[WatchlistItem]) -> tuple[list[WatchlistItem], list[WatchlistItem]]:
    fno = [w for w in watchlist if w.route == Route.FNO]
    cash = [w for w in watchlist if w.route == Route.CASH]
    return fno, cash

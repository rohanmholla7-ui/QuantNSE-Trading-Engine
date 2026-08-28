from __future__ import annotations

from collections import defaultdict

from quantnse.config import get_settings
from quantnse.models import Candle
from quantnse.timeutil import session_bucket_5m


class RVOLCalculator:
    """Intraday 5m volume vs 20-day average for the same clock bucket."""

    def __init__(self) -> None:
        self.hist: dict[str, dict[str, float]] = defaultdict(dict)

    def load_history(self, symbol: str, candles_5m: list[Candle]) -> None:
        buckets: dict[str, list[float]] = defaultdict(list)
        for c in candles_5m:
            buckets[session_bucket_5m(c.ts)].append(c.volume)
        for bucket, vols in buckets.items():
            window = vols[-20:] if len(vols) > 20 else vols
            if window:
                self.hist[symbol][bucket] = sum(window) / len(window)

    def rvol(self, symbol: str, candle_5m: Candle | None) -> float:
        if candle_5m is None:
            return 0.0
        avg = self.hist.get(symbol, {}).get(session_bucket_5m(candle_5m.ts), 0.0)
        if avg <= 0:
            return 0.0
        return candle_5m.volume / avg

    def triggered(self, symbol: str, candle_5m: Candle | None) -> bool:
        return self.rvol(symbol, candle_5m) >= get_settings().rvol_min

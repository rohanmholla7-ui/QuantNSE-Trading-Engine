from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from quantnse.models import Candle, Tick
from quantnse.timeutil import IST, to_ist


def _floor(ts: datetime, minutes: int) -> datetime:
    ts = to_ist(ts)
    minute = (ts.minute // minutes) * minutes
    return ts.replace(minute=minute, second=0, microsecond=0)


class MTFEngine:
    """Tick -> rolling 1/3/5/15 minute OHLCV plus session VWAP."""

    def __init__(self) -> None:
        self._1m: dict[str, dict[datetime, Candle]] = {}
        self._session_pv: dict[str, float] = {}
        self._session_vol: dict[str, float] = {}
        self._last_volume: dict[str, int] = {}
        self.vwap: dict[str, float] = {}

    def on_tick(self, tick: Tick) -> Candle | None:
        symbol = tick.symbol
        ts = to_ist(tick.timestamp)
        bucket = _floor(ts, 1)
        prev_vol = self._last_volume.get(symbol, 0)
        delta = max(tick.volume - prev_vol, 0) if tick.volume else tick.last_quantity
        if tick.volume:
            self._last_volume[symbol] = tick.volume
        if delta <= 0:
            delta = max(tick.last_quantity, 1)

        store = self._1m.setdefault(symbol, {})
        bar = store.get(bucket)
        px = tick.last_price
        if bar is None:
            bar = Candle(symbol=symbol, timeframe="1m", ts=bucket, open=px, high=px, low=px, close=px, volume=delta)
        else:
            bar.high = max(bar.high, px)
            bar.low = min(bar.low, px)
            bar.close = px
            bar.volume += delta
        store[bucket] = bar

        self._session_pv[symbol] = self._session_pv.get(symbol, 0.0) + px * delta
        self._session_vol[symbol] = self._session_vol.get(symbol, 0.0) + delta
        vol = self._session_vol[symbol]
        self.vwap[symbol] = self._session_pv[symbol] / vol if vol else px
        return bar

    def candles(self, symbol: str, timeframe: str, count: int = 80) -> list[Candle]:
        minutes = {"1m": 1, "3m": 3, "5m": 5, "15m": 15}[timeframe]
        ones = sorted(self._1m.get(symbol, {}).values(), key=lambda c: c.ts)
        if minutes == 1:
            return ones[-count:]
        grouped: dict[datetime, Candle] = {}
        for c in ones:
            bucket = _floor(c.ts, minutes)
            g = grouped.get(bucket)
            if g is None:
                grouped[bucket] = Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    ts=bucket,
                    open=c.open,
                    high=c.high,
                    low=c.low,
                    close=c.close,
                    volume=c.volume,
                )
            else:
                g.high = max(g.high, c.high)
                g.low = min(g.low, c.low)
                g.close = c.close
                g.volume += c.volume
        return sorted(grouped.values(), key=lambda c: c.ts)[-count:]

    def last_close(self, symbol: str) -> float | None:
        bars = self.candles(symbol, "1m", 1)
        return bars[-1].close if bars else None

    def orb_15m(self, symbol: str, session_open: datetime) -> tuple[float | None, float | None]:
        """Opening range from first 15-minute bar after 09:15 IST."""
        start = to_ist(session_open).replace(hour=9, minute=15, second=0, microsecond=0)
        end = start + timedelta(minutes=15)
        highs: list[float] = []
        lows: list[float] = []
        for c in self.candles(symbol, "1m", 400):
            if start <= c.ts < end:
                highs.append(c.high)
                lows.append(c.low)
        if not highs:
            bars = self.candles(symbol, "15m", 1)
            if bars:
                return bars[0].high, bars[0].low
            return None, None
        return max(highs), min(lows)

    def snapshot_rows(self) -> list[dict]:
        rows = []
        for symbol, bars in self._1m.items():
            for c in bars.values():
                rows.append({**c.model_dump(), "vwap": self.vwap.get(symbol)})
        return rows

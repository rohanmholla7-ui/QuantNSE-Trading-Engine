from __future__ import annotations

from datetime import datetime
from typing import Any

from quantnse.models import Tick
from quantnse.timeutil import IST


def parse_kite_tick(raw: dict[str, Any], symbol: str) -> Tick:
    depth = raw.get("depth") or {}
    buy = depth.get("buy") or []
    sell = depth.get("sell") or []
    ts = raw.get("exchange_timestamp") or raw.get("last_trade_time") or datetime.now(tz=IST)
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=IST)
    ohlc = raw.get("ohlc") or {}
    return Tick(
        instrument_token=int(raw.get("instrument_token") or 0),
        symbol=symbol,
        last_price=float(raw.get("last_price") or 0),
        volume=int(raw.get("volume") or 0),
        last_quantity=int(raw.get("last_quantity") or raw.get("last_traded_quantity") or 0),
        timestamp=ts,
        bid_qty=[int(l.get("quantity") or 0) for l in buy[:5]],
        ask_qty=[int(l.get("quantity") or 0) for l in sell[:5]],
        bid_price=[float(l.get("price") or 0) for l in buy[:5]],
        ask_price=[float(l.get("price") or 0) for l in sell[:5]],
        ohlc={k: float(v) for k, v in ohlc.items() if v is not None},
    )

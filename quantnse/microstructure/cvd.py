from __future__ import annotations

from quantnse.models import Tick


class CVDTracker:
    """Buyer-initiated (trade at ask) vs seller-initiated (trade at bid)."""

    def __init__(self) -> None:
        self.cvd: dict[str, float] = {}

    def on_tick(self, tick: Tick) -> float:
        qty = tick.last_quantity or 0
        if qty <= 0 and tick.volume:
            qty = 1
        best_bid = tick.bid_price[0] if tick.bid_price else None
        best_ask = tick.ask_price[0] if tick.ask_price else None
        delta = 0.0
        if best_ask is not None and tick.last_price >= best_ask:
            delta = float(qty)
        elif best_bid is not None and tick.last_price <= best_bid:
            delta = -float(qty)
        value = self.cvd.get(tick.symbol, 0.0) + delta
        self.cvd[tick.symbol] = value
        return value

    def value(self, symbol: str) -> float:
        return self.cvd.get(symbol, 0.0)

    def classified(self, tick: Tick) -> bool:
        return bool(tick.bid_price and tick.ask_price)

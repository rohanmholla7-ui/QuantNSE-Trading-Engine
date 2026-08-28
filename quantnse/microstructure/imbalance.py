from __future__ import annotations

from quantnse.models import Tick


def order_book_imbalance(tick: Tick, levels: int = 5) -> float:
    bid = sum(tick.bid_qty[:levels])
    ask = sum(tick.ask_qty[:levels])
    if ask <= 0:
        return float("inf") if bid > 0 else 0.0
    return bid / ask

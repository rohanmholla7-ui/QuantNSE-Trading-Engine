from __future__ import annotations

from dataclasses import dataclass

from quantnse.config import get_settings


@dataclass
class RoundTripCost:
    buy_notional: float
    sell_notional: float
    brokerage: float
    stt: float
    exchange: float
    sebi: float
    gst: float
    slippage: float
    total: float


def _brokerage(notional: float, settings) -> float:
    pct = notional * settings.brokerage_pct
    return min(settings.brokerage_flat, pct) if pct else settings.brokerage_flat


def round_trip_equity_intraday(qty: int, entry: float, exit_px: float) -> RoundTripCost:
    """Statutory cost model from PRD (equity intraday)."""
    s = get_settings()
    buy_n = qty * entry
    sell_n = qty * exit_px
    turnover = buy_n + sell_n
    brokerage = _brokerage(buy_n, s) + _brokerage(sell_n, s)
    stt = sell_n * s.stt_sell_intraday
    exchange = turnover * s.nse_txn_pct
    sebi = turnover * s.sebi_pct
    gst = s.gst_pct * (brokerage + exchange + sebi)
    slippage = (buy_n + sell_n) * s.slippage_pct
    total = brokerage + stt + exchange + sebi + gst + slippage
    return RoundTripCost(
        buy_notional=buy_n,
        sell_notional=sell_n,
        brokerage=brokerage,
        stt=stt,
        exchange=exchange,
        sebi=sebi,
        gst=gst,
        slippage=slippage,
        total=total,
    )

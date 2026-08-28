from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quantnse.gates.engine import GateContext, evaluate
from quantnse.models import Route
from quantnse.risk.costs import round_trip_equity_intraday


@dataclass
class BacktestTrade:
    symbol: str
    entry: float
    exit: float
    qty: int
    pnl: float
    costs: float
    net: float
    status: str


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    prev = close.shift(1)
    tr = pd.concat([(high - low), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def replay_longs(df: pd.DataFrame, symbol: str, route: Route, sector: str) -> list[BacktestTrade]:
    """Replay 5m bars. Uses only information available at bar close (no look-ahead)."""
    required = {"ts", "open", "high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        raise ValueError("bars missing OHLCV")
    work = df.copy().sort_values("ts").reset_index(drop=True)
    work["atr"] = _atr(work["high"], work["low"], work["close"])
    pv = (work["close"] * work["volume"]).cumsum()
    vol = work["volume"].cumsum().replace(0, 1)
    work["vwap"] = pv / vol
    day = pd.to_datetime(work["ts"]).dt.date
    orb_high = work.groupby(day)["high"].transform(lambda s: s.iloc[:3].max() if len(s) else None)
    orb_low = work.groupby(day)["low"].transform(lambda s: s.iloc[:3].min() if len(s) else None)
    trades: list[BacktestTrade] = []
    in_pos = False
    entry = stop = tp1 = qty = 0.0
    for i, row in work.iterrows():
        if i < 20:
            continue
        ctx = GateContext(
            symbol=symbol,
            route=route,
            sector=sector,
            sector_vs_open=0.2,
            vix_change_pct=1.0,
            pcr=1.2,
            call_oi_unwinding=False,
            imbalance=1.4,
            cvd=100.0,
            cvd_known=True,
            price=float(row["close"]),
            vwap=float(row["vwap"]),
            orb_high=float(orb_high.iloc[i]) if pd.notna(orb_high.iloc[i]) else float(row["high"]),
            orb_low=float(orb_low.iloc[i]) if pd.notna(orb_low.iloc[i]) else float(row["low"]),
            resistance=float(row["close"]) * 1.02,
            atr=float(row["atr"]) if pd.notna(row["atr"]) else float(row["close"]) * 0.01,
        )
        setup = evaluate(ctx)
        if not in_pos and setup.status == "triggered" and setup.entry:
            in_pos = True
            entry = setup.entry
            stop = setup.stop_loss or entry
            tp1 = setup.tp1 or entry
            qty = setup.qty
            continue
        if in_pos:
            px = float(row["low"])
            exit_px = None
            if px <= stop:
                exit_px = stop
            elif float(row["high"]) >= tp1:
                exit_px = tp1
            if exit_px is not None:
                costs = round_trip_equity_intraday(int(qty), entry, exit_px)
                pnl = (exit_px - entry) * qty
                trades.append(
                    BacktestTrade(
                        symbol=symbol,
                        entry=entry,
                        exit=exit_px,
                        qty=int(qty),
                        pnl=pnl,
                        costs=costs.total,
                        net=pnl - costs.total,
                        status=setup.status,
                    )
                )
                in_pos = False
    return trades

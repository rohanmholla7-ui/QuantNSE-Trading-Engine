from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from math import floor
from typing import Any

from quantnse.config import IST, get_settings
from quantnse.ingestion.duck import DuckStore
from quantnse.models import Setup
from quantnse.timeutil import now_ist, to_ist


def sim_qty(entry: float) -> int:
    settings = get_settings()
    if entry <= 0:
        return 0
    return max(int(floor(settings.sim_notional / entry)), 1)


def net_from_gross(gross: float, qty: int, entry: float) -> float:
    friction = qty * entry * get_settings().sim_friction
    return gross - friction


@dataclass
class OpenSim:
    symbol: str
    sector: str
    entry: float
    target: float
    sl: float
    qty: int
    opened_at: datetime
    notional: float


class PerformanceTracker:
    def __init__(self, store: DuckStore | None = None) -> None:
        self.store = store or DuckStore()
        self.open: dict[str, OpenSim] = {}

    def open_from_setup(self, setup: Setup, sector: str, ts: datetime | None = None) -> OpenSim | None:
        if setup.status != "READY_TO_ENTER" or not setup.entry or not setup.tp1 or not setup.stop_loss:
            return None
        qty = setup.qty or sim_qty(setup.entry)
        sim = OpenSim(
            symbol=setup.symbol,
            sector=sector,
            entry=setup.entry,
            target=setup.tp1,
            sl=setup.stop_loss,
            qty=qty,
            opened_at=ts or setup.created_at,
            notional=qty * setup.entry,
        )
        self.open[setup.symbol] = sim
        return sim

    def on_price(self, symbol: str, price: float, ts: datetime, high: float | None = None, low: float | None = None) -> dict[str, Any] | None:
        sim = self.open.get(symbol)
        if sim is None:
            return None
        hi = high if high is not None else price
        lo = low if low is not None else price
        local = to_ist(ts)
        cutoff = local.replace(hour=15, minute=18, second=0, microsecond=0)
        outcome = None
        exit_px = price
        if lo <= sim.sl:
            outcome, exit_px = "LOSS", sim.sl
        elif hi >= sim.target:
            outcome, exit_px = "WIN", sim.target
        elif local >= cutoff:
            outcome, exit_px = "SQUARED_OFF", price
        if outcome is None:
            return None
        return self._close(sim, exit_px, outcome, local)

    def _close(self, sim: OpenSim, exit_px: float, outcome: str, ts: datetime) -> dict[str, Any]:
        gross = sim.qty * (exit_px - sim.entry)
        net = net_from_gross(gross, sim.qty, sim.entry)
        row = {
            "ts": ts,
            "symbol": sim.symbol,
            "sector": sim.sector,
            "entry": sim.entry,
            "target": sim.target,
            "sl": sim.sl,
            "exit": exit_px,
            "qty": sim.qty,
            "notional": sim.notional,
            "gross_pnl": gross,
            "net_pnl": net,
            "outcome": outcome,
        }
        self.store.insert_trade(row)
        self.open.pop(sim.symbol, None)
        return row

    def seed(self, row: dict[str, Any]) -> None:
        self.store.insert_trade(row)

    def history(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for r in self.store.trades():
            item = dict(r)
            ts = item.get("ts")
            if ts is not None:
                aware = ts if getattr(ts, "tzinfo", None) else ts.replace(tzinfo=IST)
                item["date"] = aware.date().isoformat()
                item["ts"] = aware.isoformat()
            out.append(item)
        return out

    def metrics(self, now: datetime | None = None) -> dict[str, Any]:
        now = to_ist(now or now_ist())
        day_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
        window_start = now - timedelta(days=90)
        rows = self.store.trades()
        today = []
        rolling = []
        for r in rows:
            ts = r["ts"]
            if getattr(ts, "tzinfo", None) is None:
                ts = ts.replace(tzinfo=IST)
            else:
                ts = ts.astimezone(IST)
            if ts >= day_start:
                today.append(r)
            if ts >= window_start:
                rolling.append(r)
        wins_t = sum(1 for r in today if r["outcome"] == "WIN")
        loss_t = sum(1 for r in today if r["outcome"] == "LOSS")
        wins = [r for r in rolling if r["outcome"] == "WIN"]
        losses = [r for r in rolling if r["outcome"] == "LOSS"]
        gain = sum(float(r["gross_pnl"]) for r in wins) if wins else 0.0
        loss_abs = abs(sum(float(r["gross_pnl"]) for r in losses)) if losses else 0.0
        pf = (gain / loss_abs) if loss_abs else (gain if gain else 0.0)
        wr_den = len(wins) + len(losses)
        win_rate = (len(wins) / wr_den * 100.0) if wr_den else 0.0
        return {
            "today_pnl": sum(float(r["net_pnl"]) for r in today),
            "today_wins": wins_t,
            "today_losses": loss_t,
            "today_trades": len(today),
            "win_rate_90d": win_rate,
            "trades_90d": len(rolling),
            "profit_factor_90d": pf,
            "open_sims": list(self.open),
        }

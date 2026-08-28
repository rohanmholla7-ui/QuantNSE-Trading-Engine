from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal


Side = Literal["CE", "PE"]


@dataclass
class OptionQuote:
    strike: float
    side: Side
    oi: float
    oi_prev: float
    volume: float
    ltp: float
    iv: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0


@dataclass
class ChainSnapshot:
    symbol: str
    spot: float
    atm: float
    calls: list[OptionQuote] = field(default_factory=list)
    puts: list[OptionQuote] = field(default_factory=list)


def atm_strike(spot: float, step: float = 50.0) -> float:
    return round(spot / step) * step


def window_quotes(quotes: list[OptionQuote], atm: float, n: int = 5, step: float = 50.0) -> list[OptionQuote]:
    lo, hi = atm - n * step, atm + n * step
    return [q for q in quotes if lo <= q.strike <= hi]


def pcr(chain: ChainSnapshot, n: int = 5, step: float = 50.0) -> tuple[float, float]:
    """Strike-window volume PCR and OI PCR."""
    calls = window_quotes(chain.calls, chain.atm, n, step)
    puts = window_quotes(chain.puts, chain.atm, n, step)
    cv = sum(q.volume for q in calls) or 1.0
    pv = sum(q.volume for q in puts)
    co = sum(q.oi for q in calls) or 1.0
    po = sum(q.oi for q in puts)
    return pv / cv, po / co


def oi_delta(quotes: list[OptionQuote]) -> float:
    return sum(q.oi - q.oi_prev for q in quotes)


def classify_oi(call_d: float, put_d: float, price_up: bool) -> str:
    if price_up and call_d > 0:
        return "long_buildup"
    if price_up and call_d < 0:
        return "short_covering"
    if (not price_up) and call_d > 0:
        return "short_buildup"
    if (not price_up) and call_d < 0:
        return "long_unwinding"
    if put_d > 0 and not price_up:
        return "put_long_buildup"
    return "mixed"


def call_oi_unwinding(chain: ChainSnapshot, n: int = 5, step: float = 50.0) -> bool:
    calls = window_quotes(chain.calls, chain.atm, n, step)
    return oi_delta(calls) < 0


def max_pain(chain: ChainSnapshot) -> float:
    strikes = sorted({q.strike for q in chain.calls + chain.puts})
    if not strikes:
        return chain.atm
    best_k, best_pain = chain.atm, float("inf")
    for k in strikes:
        pain = 0.0
        for c in chain.calls:
            pain += max(k - c.strike, 0.0) * c.oi
        for p in chain.puts:
            pain += max(p.strike - k, 0.0) * p.oi
        if pain < best_pain:
            best_pain = pain
            best_k = k
    return best_k


def nearest_call_oi_wall(chain: ChainSnapshot, spot: float) -> float | None:
    above = [q for q in chain.calls if q.strike >= spot]
    if not above:
        return None
    wall = max(above, key=lambda q: q.oi)
    return wall.strike


def build_chain_from_quotes(
    symbol: str,
    spot: float,
    rows: Iterable[dict],
    step: float = 50.0,
) -> ChainSnapshot:
    atm = atm_strike(spot, step)
    calls: list[OptionQuote] = []
    puts: list[OptionQuote] = []
    for r in rows:
        q = OptionQuote(
            strike=float(r["strike"]),
            side=r["side"],
            oi=float(r.get("oi") or 0),
            oi_prev=float(r.get("oi_prev") or r.get("oi") or 0),
            volume=float(r.get("volume") or 0),
            ltp=float(r.get("ltp") or 0),
            iv=float(r.get("iv") or 0),
            delta=float(r.get("delta") or 0),
            gamma=float(r.get("gamma") or 0),
        )
        (calls if q.side == "CE" else puts).append(q)
    return ChainSnapshot(symbol=symbol, spot=spot, atm=atm, calls=calls, puts=puts)

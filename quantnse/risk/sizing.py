from __future__ import annotations

from dataclasses import dataclass

from quantnse.config import get_settings


@dataclass
class Geometry:
    entry: float
    stop: float
    tp1: float
    tp2: float
    risk: float
    reward: float
    rr: float
    qty: int
    capped: bool


def structural_stop(entry: float, vwap: float, orb_low: float) -> tuple[float, bool]:
    settings = get_settings()
    raw = max(vwap, orb_low)
    floor = entry * (1 - settings.max_risk_pct)
    if raw < floor:
        return floor, True
    if raw >= entry:
        return floor, True
    return raw, False


def geometry(
    entry: float,
    vwap: float,
    orb_low: float,
    resistance: float,
    atr: float,
    capital: float = 200_000.0,
) -> Geometry | None:
    settings = get_settings()
    stop, capped = structural_stop(entry, vwap, orb_low)
    risk = entry - stop
    if risk <= 0:
        return None
    tp1 = entry + settings.rr_min * risk
    oi_or_atr = resistance if resistance > entry else entry + 1.5 * atr
    tp2 = max(oi_or_atr, tp1)
    reward = tp1 - entry
    rr = reward / risk
    if rr < settings.rr_min:
        return None
    risk_rupees = capital * settings.max_risk_pct
    qty = int(risk_rupees / risk) if risk else 0
    qty = max(qty, 1)
    return Geometry(
        entry=entry,
        stop=stop,
        tp1=tp1,
        tp2=tp2,
        risk=risk,
        reward=reward,
        rr=rr,
        qty=qty,
        capped=capped,
    )

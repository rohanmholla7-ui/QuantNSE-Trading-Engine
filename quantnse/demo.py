from __future__ import annotations

import random
from datetime import datetime, timedelta

from quantnse.derivatives.chain import build_chain_from_quotes
from quantnse.models import MacroSnapshot, Tick


def synthetic_session(symbol: str, base: float, start: datetime, minutes: int = 45, seed: int = 7) -> list[Tick]:
    rng = random.Random(seed + len(symbol))
    ticks: list[Tick] = []
    price = base
    vol = 0
    for m in range(minutes):
        for i in range(12):
            ts = start + timedelta(minutes=m, seconds=i * 5)
            drift = 0.0004 if m >= 16 else 0.00005
            price = max(1.0, price * (1 + drift + rng.uniform(-0.0006, 0.0008)))
            last_qty = rng.randint(50, 400)
            vol += last_qty
            bid = price - 0.05
            ask = price + 0.05
            ticks.append(
                Tick(
                    instrument_token=0,
                    symbol=symbol,
                    last_price=round(price, 2),
                    volume=vol,
                    last_quantity=last_qty,
                    timestamp=ts,
                    bid_qty=[800, 600, 400, 200, 100],
                    ask_qty=[200, 180, 150, 120, 90],
                    bid_price=[bid, bid - 0.05, bid - 0.1, bid - 0.15, bid - 0.2],
                    ask_price=[ask, ask + 0.05, ask + 0.1, ask + 0.15, ask + 0.2],
                    ohlc={"open": base, "high": price, "low": base * 0.995, "close": price},
                )
            )
    return ticks


def demo_chain(symbol: str, spot: float) -> object:
    step = 50 if spot > 200 else 5
    atm = round(spot / step) * step
    rows = []
    for i in range(-5, 6):
        k = atm + i * step
        rows.append({"strike": k, "side": "CE", "oi": 12000 - i * 400, "oi_prev": 13000, "volume": 4000, "ltp": max(1, 20 - i)})
        rows.append({"strike": k, "side": "PE", "oi": 15000 + i * 200, "oi_prev": 14000, "volume": 5000, "ltp": max(1, 18 + i)})
    return build_chain_from_quotes(symbol, spot, rows, step=step)


def default_macro() -> MacroSnapshot:
    return MacroSnapshot(
        vix=13.2,
        vix_change_pct=1.1,
        vix_lockout=False,
        sector_vs_open={
            "NIFTY 50": 0.35,
            "NIFTY BANK": 0.22,
            "NIFTY AUTO": 0.4,
            "NIFTY IT": 0.18,
            "NIFTY PHARMA": 0.12,
            "NIFTY METAL": 0.3,
            "NIFTY FMCG": 0.08,
            "NIFTY PSU BANK": 0.25,
        },
        gift_nifty=24810.0,
        sp500_fut=5620.0,
        nasdaq_fut=20110.0,
        nikkei=39100.0,
        hang_seng=17650.0,
        usd_inr=83.4,
        brent=82.1,
        fii_cash=420.0,
        dii_cash=-110.0,
        bias="risk_on",
    )

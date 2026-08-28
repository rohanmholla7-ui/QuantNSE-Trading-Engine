from __future__ import annotations

from typing import Any

from quantnse.config import get_settings
from quantnse.models import MacroSnapshot
from quantnse.store import StateStore

SECTOR_YFINANCE = {
    "NIFTY 50": "^NSEI",
    "NIFTY BANK": "^NSEBANK",
    "NIFTY AUTO": "^CNXAUTO",
    "NIFTY IT": "^CNXIT",
    "NIFTY PHARMA": "^CNXPHARMA",
    "NIFTY METAL": "^CNXMETAL",
    "NIFTY FMCG": "^CNXFMCG",
    "NIFTY PSU BANK": "^CNXPSUBANK",
}

GLOBAL_TICKERS = {
    "gift_nifty": "NQ=F",  # proxy if GIFT symbol unavailable
    "sp500_fut": "ES=F",
    "nasdaq_fut": "NQ=F",
    "nikkei": "^N225",
    "hang_seng": "^HSI",
    "usd_inr": "INR=X",
    "brent": "BZ=F",
}


def compute_lockout(vix_change_pct: float, news_breaker: bool = False) -> bool:
    return news_breaker or vix_change_pct >= get_settings().vix_lockout_pct


def fii_dii_bias(fii: float | None, dii: float | None) -> str:
    net = (fii or 0) + (dii or 0)
    if net > 0:
        return "risk_on"
    if net < 0:
        return "risk_off"
    return "neutral"


def poll_yahoo_macros() -> dict[str, float | None]:
    settings = get_settings()
    if not settings.enable_yahoo_macro:
        return {k: None for k in GLOBAL_TICKERS}
    try:
        import yfinance as yf
    except ImportError:
        return {k: None for k in GLOBAL_TICKERS}
    out: dict[str, float | None] = {}
    for key, ticker in GLOBAL_TICKERS.items():
        try:
            hist = yf.Ticker(ticker).history(period="2d")
            out[key] = float(hist["Close"].iloc[-1]) if len(hist) else None
        except Exception:
            out[key] = None
    return out


def snapshot_from_state(store: StateStore) -> MacroSnapshot:
    data: dict[str, Any] = store.get_json("macro", {}) or {}
    snap = MacroSnapshot.model_validate(data) if data else MacroSnapshot()
    snap.vix_lockout = compute_lockout(snap.vix_change_pct, snap.news_breaker)
    snap.bias = fii_dii_bias(snap.fii_cash, snap.dii_cash)
    return snap

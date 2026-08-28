from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from quantnse.config import get_settings
from quantnse.models import Candle
from quantnse.timeutil import IST


def login_url() -> str:
    settings = get_settings()
    return f"https://kite.zerodha.com/connect/login?v=3&api_key={settings.kite_api_key}"


def exchange_request_token(request_token: str) -> str:
    """Exchange Kite request_token for access_token. Requires kiteconnect."""
    from kiteconnect import KiteConnect

    settings = get_settings()
    kite = KiteConnect(api_key=settings.kite_api_key)
    data = kite.generate_session(request_token, api_secret=settings.kite_api_secret)
    return str(data["access_token"])


def make_kite() -> Any:
    from kiteconnect import KiteConnect

    settings = get_settings()
    kite = KiteConnect(api_key=settings.kite_api_key)
    if settings.kite_access_token:
        kite.set_access_token(settings.kite_access_token)
    return kite


def fetch_5m_history(kite: Any, instrument_token: int, days: int = 25) -> list[Candle]:
    to = datetime.now(tz=IST)
    frm = to - timedelta(days=days)
    rows = kite.historical_data(instrument_token, frm, to, "5minute")
    out: list[Candle] = []
    for r in rows:
        ts = r["date"]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=IST)
        out.append(
            Candle(
                symbol=str(instrument_token),
                timeframe="5m",
                ts=ts,
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r["volume"]),
            )
        )
    return out


def load_instruments(kite: Any) -> list[dict[str, Any]]:
    return kite.instruments("NSE")

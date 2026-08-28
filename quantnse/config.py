from __future__ import annotations

from datetime import time
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

IST = ZoneInfo("Asia/Kolkata")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    kite_api_key: str = ""
    kite_api_secret: str = ""
    kite_access_token: str = ""
    kite_redirect_url: str = "http://127.0.0.1:5000/kite/callback"

    redis_url: str = "redis://127.0.0.1:6379/0"
    quantnse_mode: str = "demo"  # demo | live
    enable_live_orders: bool = False
    watchlist_size: int = 30
    duckdb_path: str = "data/quantnse.duckdb"
    enable_yahoo_macro: bool = True
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    rvol_min: float = 1.5
    imbalance_min: float = 1.30
    rr_min: float = 2.0
    vix_lockout_pct: float = 4.0
    max_risk_pct: float = 0.008
    slippage_pct: float = 0.0005
    brokerage_flat: float = 20.0
    brokerage_pct: float = 0.0003
    stt_sell_intraday: float = 0.00025
    nse_txn_pct: float = 0.0000297
    sebi_pct: float = 0.000001
    gst_pct: float = 0.18

    preopen_start: time = time(9, 0)
    preopen_end: time = time(9, 8)
    session_open: time = time(9, 15)
    funnel_end: time = time(9, 30)
    entry_start: time = time(9, 30)
    entry_end: time = time(14, 30)
    square_off: time = time(15, 18)
    session_close: time = time(15, 30)


@lru_cache
def get_settings() -> Settings:
    return Settings()

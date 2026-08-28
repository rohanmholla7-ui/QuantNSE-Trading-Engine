from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Route(str, Enum):
    FNO = "fno"
    CASH = "cash"


class GateName(str, Enum):
    MACRO = "gate1_macro"
    DERIVATIVES = "gate2_derivatives"
    ORDER_FLOW = "gate3_order_flow"
    PRICE_ACTION = "gate4_price_action"
    RISK_REWARD = "gate5_risk_reward"


class GateStatus(str, Enum):
    PASS = "pass"
    FAIL_DISCARD = "fail_discard"
    HOLD_STAGING = "hold_staging"
    NO_TRIGGER = "no_trigger"
    REJECT = "reject"
    SKIPPED = "skipped"


class Tick(BaseModel):
    instrument_token: int
    symbol: str
    last_price: float
    volume: int = 0
    last_quantity: int = 0
    timestamp: datetime
    bid_qty: list[int] = Field(default_factory=list)
    ask_qty: list[int] = Field(default_factory=list)
    bid_price: list[float] = Field(default_factory=list)
    ask_price: list[float] = Field(default_factory=list)
    ohlc: dict[str, float] = Field(default_factory=dict)


class Candle(BaseModel):
    symbol: str
    timeframe: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class UniverseName(BaseModel):
    symbol: str
    name: str = ""
    sector: str = "NIFTY 50"
    route: Route = Route.CASH
    instrument_token: int = 0


class WatchlistItem(BaseModel):
    symbol: str
    score: float
    rvol: float
    gap_pct: float
    route: Route
    instrument_token: int = 0
    sector: str = "NIFTY 50"


class GateResult(BaseModel):
    gate: GateName
    status: GateStatus
    reason: str
    metrics: dict[str, Any] = Field(default_factory=dict)


class Setup(BaseModel):
    symbol: str
    route: Route
    status: str
    gates: list[GateResult]
    entry: float | None = None
    stop_loss: float | None = None
    tp1: float | None = None
    tp2: float | None = None
    rr: float | None = None
    qty: int = 0
    est_cost: float = 0.0
    created_at: datetime


class MacroSnapshot(BaseModel):
    vix: float = 0.0
    vix_change_pct: float = 0.0
    vix_lockout: bool = False
    sector_vs_open: dict[str, float] = Field(default_factory=dict)
    gift_nifty: float | None = None
    sp500_fut: float | None = None
    nasdaq_fut: float | None = None
    nikkei: float | None = None
    hang_seng: float | None = None
    usd_inr: float | None = None
    brent: float | None = None
    fii_cash: float | None = None
    dii_cash: float | None = None
    bias: str = "neutral"
    news_breaker: bool = False

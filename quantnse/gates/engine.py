from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from quantnse.config import get_settings
from quantnse.models import GateName, GateResult, GateStatus, Route, Setup
from quantnse.risk.sizing import geometry
from quantnse.timeutil import now_ist


@dataclass
class GateContext:
    symbol: str
    route: Route
    sector: str
    sector_vs_open: float
    vix_change_pct: float
    pcr: float | None
    call_oi_unwinding: bool
    imbalance: float | None
    cvd: float | None
    cvd_known: bool
    price: float
    vwap: float
    orb_high: float | None
    orb_low: float | None
    resistance: float | None
    atr: float
    news_breaker: bool = False
    sector_vs_vwap: float = 0.1
    extra: dict = field(default_factory=dict)


def _result(gate: GateName, status: GateStatus, reason: str, **metrics) -> GateResult:
    return GateResult(gate=gate, status=status, reason=reason, metrics=metrics)


def evaluate(ctx: GateContext, ts: datetime | None = None) -> Setup:
    settings = get_settings()
    gates: list[GateResult] = []

    if ctx.news_breaker or ctx.vix_change_pct >= settings.vix_lockout_pct:
        gates.append(
            _result(
                GateName.MACRO,
                GateStatus.FAIL_DISCARD,
                "VIX/news circuit breaker",
                vix_change_pct=ctx.vix_change_pct,
                news_breaker=ctx.news_breaker,
            )
        )
        return _setup(ctx, "discarded", gates, ts)

    if ctx.sector_vs_open <= 0:
        gates.append(
            _result(
                GateName.MACRO,
                GateStatus.FAIL_DISCARD,
                "Sector index not above open",
                sector=ctx.sector,
                sector_vs_open=ctx.sector_vs_open,
            )
        )
        return _setup(ctx, "discarded", gates, ts)

    gates.append(
        _result(
            GateName.MACRO,
            GateStatus.PASS,
            "Sector above open; VIX regime ok",
            sector_vs_open=ctx.sector_vs_open,
            vix_change_pct=ctx.vix_change_pct,
        )
    )

    if ctx.route == Route.CASH:
        gates.append(_result(GateName.DERIVATIVES, GateStatus.SKIPPED, "Cash-only route"))
    else:
        pcr_ok = ctx.pcr is not None and ctx.pcr >= 1.0
        if not (pcr_ok or ctx.call_oi_unwinding):
            gates.append(
                _result(
                    GateName.DERIVATIVES,
                    GateStatus.FAIL_DISCARD,
                    "PCR < 1.0 and no Call OI unwinding",
                    pcr=ctx.pcr,
                    call_oi_unwinding=ctx.call_oi_unwinding,
                )
            )
            return _setup(ctx, "discarded", gates, ts)
        gates.append(
            _result(
                GateName.DERIVATIVES,
                GateStatus.PASS,
                "PCR or Call OI unwinding",
                pcr=ctx.pcr,
                call_oi_unwinding=ctx.call_oi_unwinding,
            )
        )

    imb_ok = ctx.imbalance is not None and ctx.imbalance >= settings.imbalance_min
    cvd_ok = ctx.cvd_known and ctx.cvd is not None and ctx.cvd > 0
    if not ctx.cvd_known or not imb_ok or not cvd_ok:
        gates.append(
            _result(
                GateName.ORDER_FLOW,
                GateStatus.HOLD_STAGING,
                "Imbalance/CVD not confirmed — hold staging",
                imbalance=ctx.imbalance,
                cvd=ctx.cvd,
                cvd_known=ctx.cvd_known,
            )
        )
        return _setup(ctx, "staging", gates, ts)
    gates.append(
        _result(
            GateName.ORDER_FLOW,
            GateStatus.PASS,
            "Book imbalance and positive delta",
            imbalance=ctx.imbalance,
            cvd=ctx.cvd,
        )
    )

    if ctx.orb_high is None or not (ctx.price > ctx.vwap and ctx.price > ctx.orb_high):
        gates.append(
            _result(
                GateName.PRICE_ACTION,
                GateStatus.NO_TRIGGER,
                "Need price > VWAP and 15m ORB high",
                price=ctx.price,
                vwap=ctx.vwap,
                orb_high=ctx.orb_high,
            )
        )
        return _setup(ctx, "no_trigger", gates, ts)
    gates.append(
        _result(
            GateName.PRICE_ACTION,
            GateStatus.PASS,
            "VWAP + ORB breakout",
            price=ctx.price,
            vwap=ctx.vwap,
            orb_high=ctx.orb_high,
        )
    )

    if ctx.orb_low is None or ctx.resistance is None:
        gates.append(_result(GateName.RISK_REWARD, GateStatus.REJECT, "Missing SL/resistance geometry"))
        return _setup(ctx, "rejected", gates, ts)

    geo = geometry(ctx.price, ctx.vwap, ctx.orb_low, ctx.resistance, ctx.atr)
    if geo is None or geo.rr < settings.rr_min:
        gates.append(
            _result(
                GateName.RISK_REWARD,
                GateStatus.REJECT,
                "R:R below 1:2 or invalid SL",
                rr=None if geo is None else geo.rr,
            )
        )
        return _setup(ctx, "rejected", gates, ts)

    gates.append(
        _result(
            GateName.RISK_REWARD,
            GateStatus.PASS,
            "R:R >= 1:2 with structural SL",
            rr=geo.rr,
            stop=geo.stop,
            tp1=geo.tp1,
            tp2=geo.tp2,
            qty=geo.qty,
        )
    )

    if ctx.sector_vs_vwap <= 0:
        gates.append(
            _result(
                GateName.SECTOR_RS,
                GateStatus.FAIL_DISCARD,
                "Sector index not above sector session VWAP",
                sector_vs_vwap=ctx.sector_vs_vwap,
            )
        )
        return _setup(ctx, "discarded", gates, ts)
    gates.append(
        _result(
            GateName.SECTOR_RS,
            GateStatus.PASS,
            "Sector RS: index > sector VWAP",
            sector_vs_vwap=ctx.sector_vs_vwap,
        )
    )

    if ctx.orb_high is not None and ctx.orb_low is not None and ctx.atr > 0:
        orb_range = ctx.orb_high - ctx.orb_low
        if orb_range > settings.orb_atr_mult * ctx.atr:
            gates.append(
                _result(
                    GateName.ORB_EXHAUSTION,
                    GateStatus.REJECT,
                    "ORB range exhausted vs ATR14",
                    orb_range=orb_range,
                    atr=ctx.atr,
                )
            )
            return _setup(ctx, "rejected", gates, ts)
    gates.append(
        _result(
            GateName.ORB_EXHAUSTION,
            GateStatus.PASS,
            "ORB range within 2.5x ATR14",
            orb_high=ctx.orb_high,
            orb_low=ctx.orb_low,
            atr=ctx.atr,
        )
    )

    if ctx.imbalance is None or ctx.imbalance < settings.imbalance_strict:
        gates.append(
            _result(
                GateName.DEPTH_IMBALANCE,
                GateStatus.HOLD_STAGING,
                "Top-5 bid/ask imbalance < 1.4",
                imbalance=ctx.imbalance,
            )
        )
        return _setup(ctx, "staging", gates, ts)
    gates.append(
        _result(
            GateName.DEPTH_IMBALANCE,
            GateStatus.PASS,
            "Top-5 imbalance >= 1.4",
            imbalance=ctx.imbalance,
        )
    )

    if ctx.vwap <= 0:
        prox = 1.0
    else:
        prox = abs(ctx.price - ctx.vwap) / ctx.vwap
    if prox > settings.vwap_proximity_max:
        gates.append(
            _result(
                GateName.VWAP_PROXIMITY,
                GateStatus.REJECT,
                "Price extended > 0.5% from VWAP",
                proximity=prox,
            )
        )
        return _setup(ctx, "rejected", gates, ts)
    gates.append(
        _result(
            GateName.VWAP_PROXIMITY,
            GateStatus.PASS,
            "VWAP proximity <= 0.5%",
            proximity=prox,
        )
    )

    sim_qty = int(settings.sim_notional // geo.entry) if geo.entry else 0
    sim_qty = max(sim_qty, 1)
    friction = sim_qty * geo.entry * settings.sim_friction
    return _setup(
        ctx,
        "READY_TO_ENTER",
        gates,
        ts,
        entry=geo.entry,
        stop=geo.stop,
        tp1=geo.tp1,
        tp2=geo.tp2,
        rr=geo.rr,
        qty=sim_qty,
        est_cost=friction,
    )


def _setup(
    ctx: GateContext,
    status: str,
    gates: list[GateResult],
    ts: datetime | None,
    entry: float | None = None,
    stop: float | None = None,
    tp1: float | None = None,
    tp2: float | None = None,
    rr: float | None = None,
    qty: int = 0,
    est_cost: float = 0.0,
) -> Setup:
    return Setup(
        symbol=ctx.symbol,
        route=ctx.route,
        status=status,
        gates=gates,
        entry=entry,
        stop_loss=stop,
        tp1=tp1,
        tp2=tp2,
        rr=rr,
        qty=qty,
        est_cost=est_cost,
        created_at=ts or now_ist(),
    )

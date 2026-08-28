from __future__ import annotations

from quantnse.engine import QuantEngine
from quantnse.macro.context import poll_yahoo_macros
from quantnse.store import StateStore
from quantnse.workers.celery_app import celery_app


def _engine() -> QuantEngine:
    from quantnse.config import get_settings

    return QuantEngine(StateStore(get_settings().redis_url))


@celery_app.task(name="quantnse.workers.tasks.preopen_poll")
def preopen_poll() -> dict:
    eng = _engine()
    macros = poll_yahoo_macros()
    snap = eng.macro()
    for k, v in macros.items():
        if v is not None:
            setattr(snap, k, v)
    eng.set_macro(snap)
    return {"macro": snap.model_dump()}


@celery_app.task(name="quantnse.workers.tasks.run_morning_funnel")
def run_morning_funnel() -> dict:
    eng = _engine()
    items = eng.lock_watchlist()
    return {"n": len(items), "symbols": [i.symbol for i in items]}


@celery_app.task(name="quantnse.workers.tasks.square_off_alert")
def square_off_alert() -> dict:
    eng = _engine()
    for symbol in eng.watch_symbols():
        eng._square_off(symbol)
    return {"alerts": len(eng.square_off_alerts)}


@celery_app.task(name="quantnse.workers.tasks.ingest_fii_dii")
def ingest_fii_dii(fii: float = 0.0, dii: float = 0.0) -> dict:
    eng = _engine()
    snap = eng.macro()
    snap.fii_cash = fii
    snap.dii_cash = dii
    eng.set_macro(snap)
    return snap.model_dump()

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Query, WebSocket
from fastapi.responses import HTMLResponse

from quantnse.config import get_settings
from quantnse.engine import QuantEngine
from quantnse.macro.context import compute_lockout
from quantnse.models import MacroSnapshot
from quantnse.store import StateStore

engine: QuantEngine | None = None


def get_engine() -> QuantEngine:
    global engine
    if engine is None:
        settings = get_settings()
        engine = QuantEngine(StateStore(settings.redis_url))
    return engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_engine()
    yield


app = FastAPI(title="QuantNSE", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, Any]:
    eng = get_engine()
    return {"ok": True, "mode": eng.settings.quantnse_mode, "redis": eng.store.using_redis}


@app.get("/state")
def state() -> dict[str, Any]:
    return get_engine().dashboard_state()


@app.get("/watchlist")
def watchlist() -> dict[str, Any]:
    eng = get_engine()
    return {"items": [w.model_dump() for w in eng.watchlist]}


@app.get("/setups")
def setups() -> dict[str, Any]:
    eng = get_engine()
    return {"items": [s.model_dump() for s in eng.setups.values()]}


@app.post("/kill-switch")
def kill_switch(active: bool = Query(True)) -> dict[str, Any]:
    eng = get_engine()
    eng.news_breaker = active
    snap = eng.macro()
    snap.news_breaker = active
    snap.vix_lockout = compute_lockout(snap.vix_change_pct, active)
    eng.set_macro(snap)
    return {"news_breaker": active, "vix_lockout": snap.vix_lockout}


@app.post("/macro")
def set_macro(snap: MacroSnapshot) -> dict[str, Any]:
    get_engine().set_macro(snap)
    return {"ok": True}


@app.post("/demo")
def run_demo() -> dict[str, Any]:
    from quantnse.live import demo_loop

    eng = get_engine()
    demo_loop(eng)
    return {"watchlist": len(eng.watchlist), "setups": len(eng.setups)}


@app.post("/funnel")
def funnel() -> dict[str, Any]:
    items = get_engine().lock_watchlist()
    return {"items": [w.model_dump() for w in items]}


@app.post("/evaluate")
def evaluate() -> dict[str, Any]:
    setups = get_engine().evaluate_watchlist()
    return {"items": [s.model_dump() for s in setups]}


@app.get("/kite/login")
def kite_login() -> HTMLResponse:
    from quantnse.ingestion.auth import login_url

    url = login_url()
    return HTMLResponse(f'<a href="{url}">Open Kite login</a>')


@app.get("/kite/callback")
def kite_callback(request_token: str = "") -> dict[str, Any]:
    from quantnse.ingestion.auth import exchange_request_token

    if not request_token:
        return {"error": "missing request_token"}
    token = exchange_request_token(request_token)
    return {"access_token": token, "hint": "Set KITE_ACCESS_TOKEN in .env"}


@app.websocket("/ws")
async def ws_feed(ws: WebSocket) -> None:
    await ws.accept()
    await ws.send_json(get_engine().dashboard_state())
    await ws.close()

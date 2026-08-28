from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

API = os.environ.get("QUANTNSE_API", "http://127.0.0.1:8000")

st.set_page_config(page_title="QuantNSE", layout="wide")
st.title("QuantNSE Intraday Confluence")
st.caption("Decision-support only. Not investment advice. Personal analytical use.")


@st.cache_data(ttl=2)
def load_state() -> dict:
    try:
        r = requests.get(f"{API}/state", timeout=2)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"error": str(exc), "setups": [], "watchlist": [], "macro": {}, "disclaimer": ""}


state = load_state()
if state.get("error"):
    st.warning(f"API offline ({state['error']}). Start with `python -m quantnse.cli api` then `python -m quantnse.cli demo`.")

macro = state.get("macro") or {}
lockout = bool(macro.get("vix_lockout"))
if lockout:
    st.error("KILL SWITCH — India VIX regime or news circuit breaker. No new entries.")
else:
    st.success("Gates live — VIX lockout inactive")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Mode", state.get("mode", "demo"))
c2.metric("India VIX Δ%", f"{macro.get('vix_change_pct', 0):.2f}")
c3.metric("Bias", macro.get("bias", "neutral"))
c4.metric("Live orders", "ON" if state.get("live_orders") else "OFF")

cols = st.columns(3)
if cols[0].button("Load demo session"):
    requests.post(f"{API}/demo", timeout=60)
    st.cache_data.clear()
    st.rerun()
if cols[1].button("Run funnel"):
    requests.post(f"{API}/funnel", timeout=10)
    st.cache_data.clear()
    st.rerun()
if cols[2].button("Evaluate gates"):
    requests.post(f"{API}/evaluate", timeout=10)
    st.cache_data.clear()
    st.rerun()

kill = st.toggle("Manual news/geopolitics breaker", value=bool(macro.get("news_breaker")))
if kill != bool(macro.get("news_breaker")):
    requests.post(f"{API}/kill-switch", params={"active": kill}, timeout=5)
    st.cache_data.clear()
    st.rerun()

tab1, tab2, tab3, tab4 = st.tabs(["Watchlist", "Setups", "Square-off", "Macro"])

with tab1:
    wl = state.get("watchlist") or []
    st.dataframe(pd.DataFrame(wl) if wl else pd.DataFrame(), use_container_width=True)

with tab2:
    setups = state.get("setups") or []
    rows = []
    for s in setups:
        last = (s.get("gates") or [{}])[-1]
        rows.append(
            {
                "symbol": s.get("symbol"),
                "route": s.get("route"),
                "status": s.get("status"),
                "last_gate": last.get("gate"),
                "reason": last.get("reason"),
                "entry": s.get("entry"),
                "SL": s.get("stop_loss"),
                "TP1": s.get("tp1"),
                "TP2": s.get("tp2"),
                "R:R": s.get("rr"),
                "qty": s.get("qty"),
                "est_cost": s.get("est_cost"),
            }
        )
    st.dataframe(pd.DataFrame(rows) if rows else pd.DataFrame(), use_container_width=True)

with tab3:
    st.write("Hard liquidation alert at 15:18 IST (broker MIS penalty window).")
    st.json(state.get("square_off") or [])

with tab4:
    st.json(macro)

st.info(state.get("disclaimer") or "")
st.caption("News and geopolitics are a protective kill-switch only — never a trade trigger.")

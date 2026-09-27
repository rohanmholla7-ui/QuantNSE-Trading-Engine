from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

API = os.environ.get("QUANTNSE_API", "http://127.0.0.1:8000")

st.set_page_config(page_title="QuantNSE v2", layout="wide")
st.title("QuantNSE Intraday Confluence")
st.caption("Decision-support only. Not investment advice. Personal analytical use. Simulated ₹10,000 per trade.")


@st.cache_data(ttl=2)
def load_state() -> dict:
    try:
        r = requests.get(f"{API}/state", timeout=2)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"error": str(exc), "setups": [], "watchlist": [], "macro": {}, "metrics": {}, "history": [], "disclaimer": ""}


state = load_state()
if state.get("error"):
    st.warning(f"API offline ({state['error']}). Start with `python -m quantnse.cli api` then load a demo session.")

macro = state.get("macro") or {}
metrics = state.get("metrics") or {}
lockout = bool(macro.get("vix_lockout"))
if lockout:
    st.error("KILL SWITCH — India VIX regime or news circuit breaker. No new entries.")
else:
    st.success("Gates live — VIX lockout inactive")

today_pnl = float(metrics.get("today_pnl") or 0)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Today's Simulated PnL (₹10k/trade)", f"₹{today_pnl:,.0f}")
k2.metric("Today's Trade Ratio", f"{metrics.get('today_wins', 0)} Wins / {metrics.get('today_losses', 0)} Loss")
k3.metric("90-Day Rolling Accuracy", f"{metrics.get('win_rate_90d', 0):.1f}% ({metrics.get('trades_90d', 0)} trades)")
k4.metric("90-Day Profit Factor", f"{metrics.get('profit_factor_90d', 0):.2f}")
if today_pnl > 0:
    st.markdown(":green[Today net PnL is positive]")
elif today_pnl < 0:
    st.markdown(":red[Today net PnL is negative]")

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
if cols[1].button("Refresh 19-stock watchlist"):
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

tab1, tab2, tab3, tab4 = st.tabs(["Watchlist", "Historical Accuracy & Performance", "Square-off", "Macro"])

with tab1:
    wl = state.get("watchlist") or []
    setups = {s.get("symbol"): s for s in (state.get("setups") or [])}
    rows = []
    for w in wl:
        s = setups.get(w.get("symbol"), {})
        last = (s.get("gates") or [{}])[-1]
        rows.append(
            {
                "symbol": w.get("symbol"),
                "segment": w.get("segment"),
                "sector": w.get("sector"),
                "last_price": w.get("last_price"),
                "rvol": w.get("rvol"),
                "sector_rs": w.get("sector_rs"),
                "status": s.get("status"),
                "active_gates": ", ".join(w.get("active_gates") or []),
                "last_gate": last.get("gate"),
                "reason": last.get("reason"),
            }
        )
    st.dataframe(pd.DataFrame(rows) if rows else pd.DataFrame(), use_container_width=True)

with tab2:
    hist = state.get("history") or []
    hdf = pd.DataFrame(hist)
    q = st.text_input("Search symbol / sector / outcome")
    if not hdf.empty:
        hdf = hdf.rename(
            columns={
                "date": "Date",
                "symbol": "Symbol",
                "sector": "Sector",
                "entry": "Entry",
                "target": "Target",
                "sl": "SL",
                "exit": "Exit",
                "net_pnl": "PnL (₹10k slice)",
                "outcome": "Outcome",
            }
        )
        show_cols = [c for c in ["Date", "Symbol", "Sector", "Entry", "Target", "SL", "Exit", "PnL (₹10k slice)", "Outcome"] if c in hdf.columns]
        view = hdf[show_cols] if show_cols else hdf
        if q:
            mask = view.astype(str).apply(lambda col: col.str.contains(q, case=False, na=False)).any(axis=1)
            view = view[mask]
        st.dataframe(view, use_container_width=True)
        st.download_button("Download CSV", view.to_csv(index=False).encode("utf-8"), "quantnse_trade_log.csv", "text/csv")
    else:
        st.info("No closed simulated trades yet.")

with tab3:
    st.write("Hard liquidation alert at 15:18 IST (broker MIS penalty window).")
    st.json(state.get("square_off") or [])

with tab4:
    st.json(macro)

st.info(state.get("disclaimer") or "")
st.caption("News and geopolitics are a protective kill-switch only — never a trade trigger.")

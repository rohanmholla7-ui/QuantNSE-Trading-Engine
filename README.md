# QuantNSE

Intraday confluence and decision-support engine for NSE (PRD v1.0). Hierarchical gates, Kite Connect ingestion, Indian statutory cost model. **Not investment advice.** Live orders stay off unless `ENABLE_LIVE_ORDERS=true`.

## Stack

- Python 3.11+, FastAPI, Streamlit, Redis, DuckDB, Celery, Kite Connect

## Quick start (demo, no broker)

```powershell
cd "C:\Users\rohan\stock predictor"
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
docker compose up -d
python -m quantnse.cli demo
python -m quantnse.cli api
```

In another terminal:

```powershell
streamlit run app/dashboard.py
```

If Redis is down, the engine uses an in-process store (single process only).

## Kite live path

1. Create a Kite Connect app and put `KITE_API_KEY` / `KITE_API_SECRET` in `.env`.
2. `python -m quantnse.cli login` and complete OAuth (`/kite/callback` on the API).
3. Set `KITE_ACCESS_TOKEN` and `QUANTNSE_MODE=live`.
4. `python -m quantnse.cli live` — pre-market quotes on the universe, then `mode=full` depth on the 25–30 name watchlist after 09:30.

Retail Kite depth is **top 5 (L2)**, not L3 top-20. CVD uses last trade vs bid/ask; if the tape cannot be classified, Gate 3 **holds staging**.

## Session clock (IST)

| Window | Behavior |
|---|---|
| 09:00–09:08 | Pre-open / sector quotes (Celery `preopen_poll`) |
| 09:15–09:30 | Funnel Nifty-500 seed → top 30 |
| 09:30–14:30 | Entry gates |
| 15:18 | Square-off **alerts** (orders only if live flag on) |

## Gates

1. Sector index > open and VIX change < +4% (news/VIX = kill-switch only)
2. F&O: PCR ≥ 1.0 or Call OI unwinding; **cash-only skips this gate**
3. Top-5 imbalance ≥ 1.30 and CVD > 0, else staging
4. Price > session VWAP and 15m ORB high
5. Structural SL (max VWAP / ORB low, 0.8% cap) and R:R ≥ 1:2

Replace [`quantnse/universe/seed.py`](quantnse/universe/seed.py) with official Nifty 500 + F&O lists via `data/nifty500.csv` and `data/fo_symbols.csv`.

## Tests

```powershell
pytest -q
```

## Celery (optional)

Windows: `celery -A quantnse.workers.celery_app worker --pool=solo` and `celery -A quantnse.workers.celery_app beat`.

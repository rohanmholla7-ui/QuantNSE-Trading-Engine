"""Static 19-name Mid/Large-cap universe (QuantNSE v2)."""

from __future__ import annotations

TARGET_UNIVERSE: list[dict[str, str]] = [
    {"symbol": "HDFCBANK", "segment": "LARGE_CAP", "sector": "NIFTY BANK"},
    {"symbol": "ITC", "segment": "LARGE_CAP", "sector": "NIFTY FMCG"},
    {"symbol": "HINDALCO", "segment": "LARGE_CAP", "sector": "NIFTY METAL"},
    {"symbol": "VEDL", "segment": "LARGE_CAP", "sector": "NIFTY METAL"},
    {"symbol": "HINDZINC", "segment": "LARGE_CAP", "sector": "NIFTY METAL"},
    {"symbol": "BHARATFORG", "segment": "LARGE_MID", "sector": "NIFTY AUTO"},
    {"symbol": "DIXON", "segment": "LARGE_MID", "sector": "NIFTY 500"},
    {"symbol": "NMDC", "segment": "LARGE_MID", "sector": "NIFTY METAL"},
    {"symbol": "NATIONALUM", "segment": "MID_CAP", "sector": "NIFTY METAL"},
    {"symbol": "HINDCOPPER", "segment": "MID_CAP", "sector": "NIFTY METAL"},
    {"symbol": "SCI", "segment": "MID_CAP", "sector": "NIFTY 500"},
    {"symbol": "NLCINDIA", "segment": "MID_CAP", "sector": "NIFTY 500"},
    {"symbol": "SONACOMS", "segment": "MID_CAP", "sector": "NIFTY AUTO"},
    {"symbol": "ENDURANCE", "segment": "MID_CAP", "sector": "NIFTY AUTO"},
    {"symbol": "KALYANKJIL", "segment": "MID_CAP", "sector": "NIFTY 500"},
    {"symbol": "ZENSARTECH", "segment": "MID_TECH", "sector": "NIFTY IT"},
    {"symbol": "SONATSOFTW", "segment": "MID_TECH", "sector": "NIFTY IT"},
    {"symbol": "NEWGEN", "segment": "MID_TECH", "sector": "NIFTY IT"},
    {"symbol": "MAPMYINDIA", "segment": "MID_TECH", "sector": "NIFTY IT"},
]

FO_SYMBOLS = {
    "HDFCBANK",
    "ITC",
    "HINDALCO",
    "VEDL",
    "HINDZINC",
    "BHARATFORG",
    "DIXON",
    "NMDC",
    "NATIONALUM",
    "HINDCOPPER",
    "NLCINDIA",
    "SONACOMS",
}


def unique_seed() -> list[tuple[str, str, str]]:
    return [(row["symbol"], row["symbol"], row["sector"]) for row in TARGET_UNIVERSE]

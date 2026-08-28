from __future__ import annotations

import csv
from pathlib import Path

from quantnse.models import Route, UniverseName
from quantnse.universe.seed import FO_SYMBOLS, unique_seed

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

SECTOR_INDEX = {
    "BANK": "NIFTY BANK",
    "AUTO": "NIFTY AUTO",
    "IT": "NIFTY IT",
    "PHARMA": "NIFTY PHARMA",
    "METAL": "NIFTY METAL",
    "FMCG": "NIFTY FMCG",
    "PSUBANK": "NIFTY PSU BANK",
    "DEFAULT": "NIFTY 50",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_universe() -> list[UniverseName]:
    fo = set(FO_SYMBOLS)
    for row in _read_csv(DATA / "fo_symbols.csv"):
        if row.get("symbol"):
            fo.add(row["symbol"].strip().upper())

    csv_rows = _read_csv(DATA / "nifty500.csv")
    if csv_rows:
        raw = [
            (
                r["symbol"].strip().upper(),
                r.get("name", r["symbol"]),
                r.get("sector", "DEFAULT").strip().upper(),
            )
            for r in csv_rows
        ]
    else:
        raw = unique_seed()

    names: list[UniverseName] = []
    seen: set[str] = set()
    for symbol, name, sector_key in raw:
        if symbol in seen:
            continue
        seen.add(symbol)
        names.append(
            UniverseName(
                symbol=symbol,
                name=name,
                sector=SECTOR_INDEX.get(sector_key.upper(), SECTOR_INDEX["DEFAULT"]),
                route=Route.FNO if symbol in fo else Route.CASH,
            )
        )
    return names


def by_symbol(universe: list[UniverseName] | None = None) -> dict[str, UniverseName]:
    return {n.symbol: n for n in (universe or load_universe())}

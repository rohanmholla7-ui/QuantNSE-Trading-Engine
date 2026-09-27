from __future__ import annotations

from quantnse.models import Route, UniverseName
from quantnse.universe.seed import FO_SYMBOLS, TARGET_UNIVERSE


def load_universe() -> list[UniverseName]:
    names: list[UniverseName] = []
    for row in TARGET_UNIVERSE:
        symbol = row["symbol"].upper()
        names.append(
            UniverseName(
                symbol=symbol,
                name=symbol,
                sector=row["sector"],
                segment=row["segment"],
                route=Route.FNO if symbol in FO_SYMBOLS else Route.CASH,
            )
        )
    return names


def by_symbol(universe: list[UniverseName] | None = None) -> dict[str, UniverseName]:
    return {n.symbol: n for n in (universe or load_universe())}


def allowed_symbols() -> set[str]:
    return {row["symbol"].upper() for row in TARGET_UNIVERSE}

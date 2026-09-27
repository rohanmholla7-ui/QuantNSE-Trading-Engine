from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from quantnse.config import get_settings
from quantnse.ingestion.candles import MTFEngine


class DuckStore:
    def __init__(self, path: str | None = None) -> None:
        settings = get_settings()
        self.path = Path(path or settings.duckdb_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(self.path))
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS candles (
                symbol TEXT,
                timeframe TEXT,
                ts TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                vwap DOUBLE
            )
            """
        )
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_logs (
                ts TIMESTAMP,
                symbol TEXT,
                sector TEXT,
                entry DOUBLE,
                target DOUBLE,
                sl DOUBLE,
                exit DOUBLE,
                qty INTEGER,
                notional DOUBLE,
                gross_pnl DOUBLE,
                net_pnl DOUBLE,
                outcome TEXT
            )
            """
        )

    def persist_engine(self, engine: MTFEngine) -> None:
        rows = engine.snapshot_rows()
        if not rows:
            return
        self.con.executemany(
            "INSERT INTO candles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    r["symbol"],
                    r["timeframe"],
                    r["ts"],
                    r["open"],
                    r["high"],
                    r["low"],
                    r["close"],
                    r["volume"],
                    r.get("vwap"),
                )
                for r in rows
            ],
        )

    def insert_trade(self, row: dict[str, Any]) -> None:
        self.con.execute(
            """
            INSERT INTO trade_logs
            (ts, symbol, sector, entry, target, sl, exit, qty, notional, gross_pnl, net_pnl, outcome)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                row["ts"],
                row["symbol"],
                row.get("sector"),
                row["entry"],
                row["target"],
                row["sl"],
                row["exit"],
                row["qty"],
                row["notional"],
                row["gross_pnl"],
                row["net_pnl"],
                row["outcome"],
            ],
        )

    def trades(self) -> list[dict[str, Any]]:
        return self.con.execute(
            "SELECT * FROM trade_logs ORDER BY ts DESC"
        ).fetchdf().to_dict("records")


CandleStore = DuckStore

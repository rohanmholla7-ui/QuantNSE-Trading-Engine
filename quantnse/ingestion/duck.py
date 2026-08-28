from __future__ import annotations

from pathlib import Path

import duckdb

from quantnse.config import get_settings
from quantnse.ingestion.candles import MTFEngine


class CandleStore:
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

    def load_5m(self, symbol: str) -> list[dict]:
        return self.con.execute(
            "SELECT * FROM candles WHERE symbol = ? AND timeframe = '1m' ORDER BY ts",
            [symbol],
        ).fetchdf().to_dict("records")

"""
data/setup_db.py
────────────────
Loads NIFTY50_all.csv (from Kaggle) into a local SQLite database.
Run once before starting the agent:
    python data/setup_db.py
"""

import os
import sqlite3
import pandas as pd

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "NIFTY50_all.csv")
DB_PATH  = os.path.join(BASE_DIR, "nifty50.db")


def create_and_populate():
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(
            f"\n❌  CSV not found: {CSV_PATH}\n"
            "    Please download NIFTY50_all.csv from Kaggle and place it in the data/ folder.\n"
            "    URL: https://www.kaggle.com/datasets/rohanrao/nifty50-stock-market-data"
        )

    print(f"📂  Reading CSV: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)

    # Normalize column names → lowercase, strip spaces
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    print(f"    Columns detected: {list(df.columns)}")
    print(f"    Rows: {len(df):,}")

    # Rename common Kaggle column variants for consistency
    rename_map = {
        "symbol":        "symbol",
        "date":          "date",
        "open":          "open",
        "high":          "high",
        "low":           "low",
        "close":         "close",
        "last":          "last",
        "volume":        "volume",
        "turnover":      "turnover",
        "trades":        "trades",
        "deliverable_volume": "deliverable_volume",
        "%deliverble":   "pct_deliverable",
    }
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

    # Ensure required columns exist
    required = ["symbol", "date", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}\nActual columns: {list(df.columns)}")

    # Clean up
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df.dropna(subset=["symbol", "date", "close"], inplace=True)

    # ── Write to SQLite ───────────────────────────────────────────────────────
    print(f"\n💾  Writing to SQLite: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS stocks")
    cursor.execute("""
        CREATE TABLE stocks (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol              TEXT    NOT NULL,
            date                TEXT    NOT NULL,
            open                REAL,
            high                REAL,
            low                 REAL,
            close               REAL    NOT NULL,
            last                REAL,
            volume              REAL,
            turnover            REAL,
            trades              REAL,
            deliverable_volume  REAL,
            pct_deliverable     REAL
        )
    """)

    # Select only columns that exist in both df and schema
    schema_cols = ["symbol","date","open","high","low","close","last",
                   "volume","turnover","trades","deliverable_volume","pct_deliverable"]
    cols_to_insert = [c for c in schema_cols if c in df.columns]
    df[cols_to_insert].to_sql("stocks", conn, if_exists="append", index=False)

    # Index for fast lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON stocks(symbol)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_date   ON stocks(date)")
    conn.commit()
    conn.close()

    print(f"✅  Done! {len(df):,} rows loaded into stocks table.")
    print(f"    DB path: {DB_PATH}\n")


if __name__ == "__main__":
    create_and_populate()
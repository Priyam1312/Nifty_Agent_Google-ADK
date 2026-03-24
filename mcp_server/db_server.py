"""
mcp_server/db_server.py
───────────────────────
Local stdio MCP Server exposing NIFTY-50 SQLite database tools.

Tools:
  • list_symbols        — List all stock ticker symbols
  • fetch_stock_data    — Fetch OHLCV rows for a given symbol / date range
  • get_summary_stats   — Min / Max / Avg price stats per symbol
  • insert_stock_record — Insert a new stock record
  • generate_chart      — Generate chart → saves HTML file → auto-opens in browser
"""

import os
import sqlite3
import json
import subprocess
import sys
from datetime import datetime
from mcp.server.fastmcp import FastMCP

# ── Database path ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "..", "data", "nifty50.db")

# ── Charts folder — saved next to the project root ────────────────────────────
CHARTS_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "charts"))


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory for dict-like access."""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}\n"
            "Run `python data/setup_db.py` first to create it."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── FastMCP Server ─────────────────────────────────────────────────────────────
mcp = FastMCP("nifty50-db-server")


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 1 — List Symbols
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def list_symbols() -> str:
    """List all unique stock ticker symbols available in the NIFTY-50 database."""
    try:
        conn   = get_connection()
        cursor = conn.execute(
            "SELECT symbol, COUNT(*) as records FROM stocks GROUP BY symbol ORDER BY symbol"
        )
        rows = [{"symbol": r["symbol"], "records": r["records"]} for r in cursor.fetchall()]
        conn.close()
        return json.dumps({"symbols": rows, "total_symbols": len(rows)}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 2 — Fetch Stock Data
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def fetch_stock_data(
    symbol: str,
    start_date: str = "",
    end_date: str = "",
    limit: int = 50,
) -> str:
    """
    Fetch OHLCV stock records for a given symbol.

    Args:
        symbol:     Stock ticker e.g. RELIANCE, TCS, INFY
        start_date: Optional start date YYYY-MM-DD
        end_date:   Optional end date YYYY-MM-DD
        limit:      Max rows to return (default 50, max 500)
    """
    try:
        limit  = min(int(limit), 500)
        symbol = symbol.upper().strip()
        query  = "SELECT * FROM stocks WHERE symbol = ?"
        params = [symbol]
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        query += " ORDER BY date DESC LIMIT ?"
        params.append(limit)
        conn   = get_connection()
        cursor = conn.execute(query, params)
        rows   = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return json.dumps({"symbol": symbol, "count": len(rows), "records": rows}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 3 — Get Summary Statistics
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def get_summary_stats(symbol: str = "") -> str:
    """
    Get summary statistics for one or all stock symbols.

    Args:
        symbol: Stock ticker. If empty, returns stats for ALL symbols.
    """
    try:
        query = """
            SELECT
                symbol,
                COUNT(*)             AS total_records,
                MIN(date)            AS first_date,
                MAX(date)            AS last_date,
                ROUND(MIN(close),2)  AS min_close,
                ROUND(MAX(close),2)  AS max_close,
                ROUND(AVG(close),2)  AS avg_close,
                ROUND(MIN(open),2)   AS min_open,
                ROUND(MAX(open),2)   AS max_open,
                ROUND(AVG(open),2)   AS avg_open,
                ROUND(SUM(volume),0) AS total_volume
            FROM stocks
        """
        params = []
        if symbol:
            query += " WHERE symbol = ?"
            params.append(symbol.upper().strip())
        query += " GROUP BY symbol ORDER BY symbol"
        conn   = get_connection()
        cursor = conn.execute(query, params)
        rows   = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return json.dumps({"stats": rows, "count": len(rows)}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 4 — Insert Stock Record
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def insert_stock_record(
    symbol: str,
    date: str,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float = 0.0,
) -> str:
    """
    Insert a new stock price record into the database.

    Args:
        symbol:      Stock ticker e.g. RELIANCE
        date:        Date in YYYY-MM-DD format
        open_price:  Opening price
        high:        Highest price of the day
        low:         Lowest price of the day
        close:       Closing price
        volume:      Trading volume (optional)
    """
    try:
        datetime.strptime(date, "%Y-%m-%d")
        symbol = symbol.upper().strip()
        conn   = get_connection()
        conn.execute(
            "INSERT INTO stocks (symbol, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (symbol, date, open_price, high, low, close, volume),
        )
        conn.commit()
        conn.close()
        return json.dumps({
            "success": True,
            "message": f"Record inserted for {symbol} on {date}.",
            "record":  {"symbol": symbol, "date": date, "open": open_price,
                        "high": high, "low": low, "close": close, "volume": volume},
        }, indent=2)
    except ValueError as ve:
        return json.dumps({"error": f"Invalid date format. Use YYYY-MM-DD. Detail: {ve}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 5 — Generate Chart (saves HTML + auto-opens in browser)
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def generate_chart(
    symbol: str,
    chart_type: str,
    start_date: str = "",
    end_date: str = "",
    compare_symbol: str = "",
) -> str:
    """
    Generate a chart for a stock and AUTO-OPEN it in the user's browser.
    The chart is saved as an interactive HTML file using matplotlib + mpld3
    and opened immediately with the system browser — no manual steps needed.

    Chart types:
      line    → closing price trend over time
      bar     → compare avg closing prices across stocks
      volume  → trading volume over time
      ohlc    → open/high/low/close per day
      scatter → volume vs closing price correlation
      pie     → volume share across multiple stocks

    Args:
        symbol:         Primary stock ticker e.g. RELIANCE
        chart_type:     line | bar | volume | ohlc | scatter | pie
        start_date:     Optional start date YYYY-MM-DD
        end_date:       Optional end date YYYY-MM-DD
        compare_symbol: Optional second ticker for comparison (bar/pie)
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        import numpy as np
        import datetime as dt
        import io, base64

        # ── Colours ────────────────────────────────────────────────────────────
        PRIMARY   = "#2E75B6"
        SECONDARY = "#17A589"
        ACCENT    = "#E67E22"
        BG        = "#F8F9FA"
        GRID      = "#E0E0E0"

        # ── Fetch helper ───────────────────────────────────────────────────────
        def fetch(sym, s="", e="", lim=500):
            q = "SELECT date,open,high,low,close,volume FROM stocks WHERE symbol=?"
            p = [sym.upper().strip()]
            if s: q += " AND date>=?"; p.append(s)
            if e: q += " AND date<=?"; p.append(e)
            q += " ORDER BY date ASC LIMIT ?"; p.append(lim)
            conn = get_connection()
            rows = [dict(r) for r in conn.execute(q, p).fetchall()]
            conn.close()
            return rows

        rows = fetch(symbol, start_date, end_date)
        if not rows:
            return json.dumps({"error": f"No data found for {symbol}."})

        dates     = [r["date"]       for r in rows]
        closes    = [r["close"]      for r in rows]
        opens     = [r["open"]       for r in rows]
        highs     = [r["high"]       for r in rows]
        lows      = [r["low"]        for r in rows]
        vols      = [r["volume"] or 0 for r in rows]
        date_objs = [dt.datetime.strptime(d, "%Y-%m-%d") for d in dates]

        # ── Figure ─────────────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(13, 6))
        fig.patch.set_facecolor(BG)
        ax.set_facecolor(BG)
        ax.grid(True, color=GRID, linewidth=0.8, linestyle="--", alpha=0.7)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        for spine in ["left", "bottom"]:
            ax.spines[spine].set_color("#CCCCCC")

        title_suffix = ""
        if start_date and end_date:
            title_suffix = f"  ({start_date}  →  {end_date})"
        elif start_date:
            title_suffix = f"  (from {start_date})"
        elif end_date:
            title_suffix = f"  (until {end_date})"

        # ── Chart types ────────────────────────────────────────────────────────
        if chart_type == "line":
            ax.plot(date_objs, closes, color=PRIMARY, linewidth=2, label=symbol)
            ax.fill_between(date_objs, closes, alpha=0.12, color=PRIMARY)
            if compare_symbol:
                r2 = fetch(compare_symbol, start_date, end_date)
                d2 = [dt.datetime.strptime(r["date"], "%Y-%m-%d") for r in r2]
                c2 = [r["close"] for r in r2]
                ax.plot(d2, c2, color=SECONDARY, linewidth=2, label=compare_symbol)
                ax.fill_between(d2, c2, alpha=0.10, color=SECONDARY)
                ax.legend(fontsize=11)
            ax.set_title(f"{symbol} — Closing Price Trend{title_suffix}", fontsize=14, fontweight="bold", color="#1B3A6B", pad=15)
            ax.set_ylabel("Closing Price (₹)", fontsize=11, color="#566573")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=35, ha="right", fontsize=9)

        elif chart_type == "bar":
            syms = [symbol] + ([compare_symbol] if compare_symbol else [])
            avgs = []
            for s in syms:
                r2 = fetch(s, start_date, end_date)
                avgs.append(round(sum(r["close"] for r in r2) / len(r2), 2) if r2 else 0)
            colors = [PRIMARY, SECONDARY, ACCENT, "#8E44AD"]
            bars   = ax.bar(syms, avgs, color=colors[:len(syms)], width=0.5, edgecolor="white", linewidth=1.5)
            for bar, val in zip(bars, avgs):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(avgs)*0.01,
                        f"₹{val:,.2f}", ha="center", va="bottom", fontsize=11, fontweight="bold", color="#1B3A6B")
            ax.set_title(f"Average Closing Price Comparison{title_suffix}", fontsize=14, fontweight="bold", color="#1B3A6B", pad=15)
            ax.set_ylabel("Avg Closing Price (₹)", fontsize=11, color="#566573")
            ax.set_ylim(0, max(avgs) * 1.18)

        elif chart_type == "volume":
            vol_m = [v / 1_000_000 for v in vols]
            ax.bar(date_objs, vol_m, color=SECONDARY, alpha=0.8, width=2)
            ax.set_title(f"{symbol} — Trading Volume{title_suffix}", fontsize=14, fontweight="bold", color="#1B3A6B", pad=15)
            ax.set_ylabel("Volume (Millions)", fontsize=11, color="#566573")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=35, ha="right", fontsize=9)

        elif chart_type == "ohlc":
            sample = list(zip(date_objs, opens, highs, lows, closes))
            if len(sample) > 60:
                step = len(sample) // 60
                sample = sample[::step]
            for d, o, h, l, c in sample:
                color = PRIMARY if c >= o else ACCENT
                ax.plot([d, d], [l, h], color=color, linewidth=1.5)
                ax.plot([d, d], [o, c], color=color, linewidth=4)
            ax.set_title(f"{symbol} — OHLC Chart{title_suffix}", fontsize=14, fontweight="bold", color="#1B3A6B", pad=15)
            ax.set_ylabel("Price (₹)", fontsize=11, color="#566573")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=35, ha="right", fontsize=9)

        elif chart_type == "scatter":
            vol_m = [v / 1_000_000 for v in vols]
            ax.scatter(vol_m, closes, color=PRIMARY, alpha=0.5, s=20, edgecolors="none")
            if len(vol_m) > 2:
                z  = np.polyfit(vol_m, closes, 1)
                p  = np.poly1d(z)
                xp = np.linspace(min(vol_m), max(vol_m), 100)
                ax.plot(xp, p(xp), color=ACCENT, linewidth=2, linestyle="--", label="Trend")
                ax.legend(fontsize=10)
            ax.set_title(f"{symbol} — Volume vs Closing Price{title_suffix}", fontsize=14, fontweight="bold", color="#1B3A6B", pad=15)
            ax.set_xlabel("Volume (Millions)", fontsize=11, color="#566573")
            ax.set_ylabel("Closing Price (₹)", fontsize=11, color="#566573")

        elif chart_type == "pie":
            syms = [symbol]
            for s in compare_symbol.split(","):
                s = s.strip()
                if s: syms.append(s)
            tvols = []
            for s in syms:
                r2 = fetch(s, start_date, end_date)
                tvols.append(sum(r["volume"] or 0 for r in r2))
            colors = [PRIMARY, SECONDARY, ACCENT, "#8E44AD", "#E74C3C", "#1ABC9C"]
            wedges, texts, autotexts = ax.pie(
                tvols, labels=syms, colors=colors[:len(syms)],
                autopct="%1.1f%%", startangle=90,
                wedgeprops={"edgecolor": "white", "linewidth": 2},
            )
            for at in autotexts:
                at.set_fontsize(10)
                at.set_fontweight("bold")
            ax.set_title(f"Volume Share — {', '.join(syms)}{title_suffix}", fontsize=14, fontweight="bold", color="#1B3A6B", pad=15)

        else:
            return json.dumps({"error": f"Unknown chart_type '{chart_type}'. Use: line, bar, volume, ohlc, scatter, pie"})

        # ── Render matplotlib → PNG → embed in HTML ────────────────────────────
        ax.set_xlabel("Date", fontsize=11, color="#566573") if chart_type not in ["pie", "scatter", "bar"] else None
        plt.tight_layout(pad=2.0)

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close(fig)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("utf-8")

        # ── Build self-contained HTML with embedded PNG ────────────────────────
        title     = f"{symbol} — {chart_type.upper()} Chart"
        html      = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body  {{ margin:0; background:#1a1a2e; display:flex; flex-direction:column;
             align-items:center; justify-content:center; min-height:100vh;
             font-family:Arial,sans-serif; }}
    h2    {{ color:#a0c4ff; margin-bottom:16px; font-size:22px; }}
    img   {{ max-width:95vw; border-radius:12px;
             box-shadow:0 8px 32px rgba(0,0,0,0.5); }}
    p     {{ color:#888; font-size:13px; margin-top:12px; }}
  </style>
</head>
<body>
  <h2>{title}</h2>
  <img src="data:image/png;base64,{b64}" alt="{title}">
  <p>Generated by NIFTY-50 Data Analysis Agent</p>
</body>
</html>"""

        # ── Save HTML file ─────────────────────────────────────────────────────
        os.makedirs(CHARTS_DIR, exist_ok=True)
        ts       = datetime.now().strftime("%H%M%S")
        filename = f"{symbol}_{chart_type}_{ts}.html"
        filepath = os.path.join(CHARTS_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

        # ── AUTO-OPEN in browser ───────────────────────────────────────────────
        # subprocess.Popen so it doesn't block the MCP server
        if sys.platform == "darwin":           # macOS
            subprocess.Popen(["open", filepath])
        elif sys.platform.startswith("linux"): # Linux
            subprocess.Popen(["xdg-open", filepath])
        elif sys.platform == "win32":          # Windows
            subprocess.Popen(["start", filepath], shell=True)

        return json.dumps({
            "success":    True,
            "message":    f"Chart opened in your browser automatically! File saved at: {filepath}",
            "filepath":   filepath,
            "chart_type": chart_type,
            "symbol":     symbol,
        })

    except Exception as e:
        return json.dumps({"error": f"Chart generation failed: {str(e)}"})


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="stdio")
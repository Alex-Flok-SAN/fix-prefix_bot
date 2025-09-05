#!/usr/bin/env python3
"""
fetch_binance_klines.py

Download historical klines from Binance (Futures USDT-M or Spot) and save per-month PARQUET + CSV.
- Default: USDT-M Futures continuous PERPETUALs via /fapi/v1/continuousKlines
- Supports: /api/v3/klines (spot) and /fapi/v1/klines (futures symbol-based) if you prefer.

Output file pattern:
  <SYMBOL>_<TF>_<YYYY-MM>.parquet and .csv
  Example: ETHUSDT_M1_2024-01.parquet

Columns:
  ts_open_ms, open, high, low, close, volume, ts_close_ms
(All UTC milliseconds.)

Usage examples:
  python fetch_binance_klines.py --symbols ETHUSDT SOLUSDT BNBUSDT DOGEUSDT \
      --start 2024-01-01 --end 2024-03-31 --tf 1m --market futures

  # Spot instead of futures:
  python fetch_binance_klines.py --symbols ETHUSDT --market spot --tf 1m --start 2024-01-01 --end 2024-03-31

Requires: requests, pandas, pyarrow (optional but recommended for parquet).
  pip install requests pandas pyarrow
"""
import argparse
import calendar
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import sys
import math

import requests
import pandas as pd

def to_ms(dt_str: str) -> int:
    """Parse 'YYYY-MM-DD' or ISO-like and return UTC milliseconds."""
    dt = datetime.fromisoformat(dt_str.replace('Z','')).replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

def month_range_ms(start_ms: int, end_ms: int) -> List[Tuple[int,int,str]]:
    """Split [start_ms, end_ms] into calendar months: (ms_start, ms_end, 'YYYY-MM')."""
    out = []
    dt = datetime.utcfromtimestamp(start_ms/1000).replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    end_dt = datetime.utcfromtimestamp(end_ms/1000).replace(tzinfo=timezone.utc)
    while dt <= end_dt:
        y, m = dt.year, dt.month
        last_day = calendar.monthrange(y, m)[1]
        m_start = int(dt.timestamp()*1000)
        m_end_dt = dt.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999000)
        m_end = int(min(m_end_dt.timestamp()*1000, end_ms))
        out.append((max(m_start, start_ms), m_end, f"{y:04d}-{m:02d}"))
        # next month
        if m == 12:
            dt = dt.replace(year=y+1, month=1)
        else:
            dt = dt.replace(month=m+1)
    return out

BINANCE_SPOT = "https://api.binance.com"
BINANCE_FUT = "https://fapi.binance.com"

def fetch_chunk_continuous(pair: str, interval: str, start_ms: int, end_ms: int, limit: int = 1500, timeout: int = 20, retries: int = 5, backoff: float = 2.0) -> list:
    """Futures continuous klines (USDT-M PERPETUAL) by pair via /fapi/v1/continuousKlines."""
    url = f"{BINANCE_FUT}/fapi/v1/continuousKlines"
    params = {
        "pair": pair,
        "contractType": "PERPETUAL",
        "interval": interval,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": limit
    }
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries:
                raise
            print(f"[retry {attempt}/{retries}] {pair} {interval} failed: {e}")
            time.sleep(backoff * attempt)

def fetch_chunk_futures_symbol(symbol: str, interval: str, start_ms: int, end_ms: int, limit: int = 1500, timeout: int = 20, retries: int = 5, backoff: float = 2.0) -> list:
    """Futures (USDT-M) by symbol via /fapi/v1/klines."""
    url = f"{BINANCE_FUT}/fapi/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": limit
    }
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries:
                raise
            print(f"[retry {attempt}/{retries}] {symbol} {interval} failed: {e}")
            time.sleep(backoff * attempt)

def fetch_chunk_spot(symbol: str, interval: str, start_ms: int, end_ms: int, limit: int = 1000, timeout: int = 20, retries: int = 5, backoff: float = 2.0) -> list:
    """Spot klines via /api/v3/klines."""
    url = f"{BINANCE_SPOT}/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": limit
    }
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries:
                raise
            print(f"[retry {attempt}/{retries}] {symbol} {interval} failed: {e}")
            time.sleep(backoff * attempt)

def klines_to_df(raw: list) -> pd.DataFrame:
    """Map Binance kline array list to our schema (UTC ms)."""
    if not raw: 
        return pd.DataFrame(columns=["ts_open_ms","open","high","low","close","volume","ts_close_ms"])
    cols = [
        "open_time","open","high","low","close","volume","close_time",
        "quote_asset_volume","number_of_trades","taker_buy_base", "taker_buy_quote","ignore"
    ]
    df = pd.DataFrame(raw, columns=cols[:len(raw[0])])  # robust to endpoint variations
    out = pd.DataFrame({
        "ts_open_ms": df["open_time"].astype("int64"),
        "open": df["open"].astype(float),
        "high": df["high"].astype(float),
        "low": df["low"].astype(float),
        "close": df["close"].astype(float),
        "volume": df["volume"].astype(float),
        "ts_close_ms": df["close_time"].astype("int64")
    })
    return out

def save_month(df: pd.DataFrame, symbol: str, tf_key: str, ym: str, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    base = outdir / f"{symbol}_{tf_key}_{ym}"
    # Parquet
    try:
        df.to_parquet(str(base)+".parquet", index=False)
    except Exception as e:
        print(f"[warn] parquet save failed ({e}); ensure pyarrow is installed. Skipping parquet for {base.name}.")
    # CSV
    df.to_csv(str(base)+".csv", index=False)

def run(symbols: List[str], tf: str, market: str, start: str, end: str, outdir: Path, use_continuous=True):
    tf_map = {"1m":"M1","3m":"M3","5m":"M5","15m":"M15","30m":"M30","1h":"H1","4h":"H4","1d":"D1"}
    tf_key = tf_map.get(tf, tf.upper())
    start_ms = to_ms(start)
    end_ms = to_ms(end)
    months = month_range_ms(start_ms, end_ms)

    # Endpoint chooser
    fetcher = None
    if market == "futures":
        if use_continuous:
            fetcher = lambda sym, s, e: fetch_chunk_continuous(sym.replace("USDT","USDT"), tf, s, e, limit=1500, timeout=30, retries=8, backoff=2.5)
        else:
            fetcher = lambda sym, s, e: fetch_chunk_futures_symbol(sym, tf, s, e, limit=1500, timeout=30, retries=8, backoff=2.5)
    elif market == "spot":
        fetcher = lambda sym, s, e: fetch_chunk_spot(sym, tf, s, e, limit=1000, timeout=30, retries=8, backoff=2.5)
    else:
        raise ValueError("market must be 'futures' or 'spot'")

    for symbol in symbols:
        print(f"\n=== {symbol} {tf} {market} ===")
        for m_start, m_end, ym in months:
            print(f"  {ym}: downloading ... ", end="", flush=True)
            # paginate through month range
            all_rows = []
            cursor = m_start
            safety_loops = 0
            while cursor <= m_end and safety_loops < 10_000:
                chunk = fetcher(symbol, cursor, m_end)
                if not chunk:
                    # advance by one interval to avoid infinite loop
                    cursor += 60_000 if tf.endswith("m") else 3_600_000
                    time.sleep(0.15)
                    continue
                df = klines_to_df(chunk)
                all_rows.append(df)
                last_close = int(df["ts_close_ms"].iloc[-1])
                cursor = last_close + 1
                # Binance friendly pacing
                time.sleep(0.2)
                safety_loops += 1
                # stop if no progress
                if len(df) == 1 and df["ts_open_ms"].iloc[0] < m_start and df["ts_close_ms"].iloc[0] > m_end:
                    break
            if all_rows:
                month_df = pd.concat(all_rows, ignore_index=True)
                # trim to month exact
                month_df = month_df[(month_df["ts_open_ms"]>=m_start) & (month_df["ts_open_ms"]<=m_end)].reset_index(drop=True)
                save_month(month_df, symbol, tf_key, ym, outdir)
                print(f"saved {len(month_df)} rows.")
            else:
                print("no data.")
    print("\nDone.")

def main():
    ap = argparse.ArgumentParser(description="Fetch Binance klines and save per-month parquet+csv.")
    ap.add_argument("--symbols", nargs="+", required=False, default=None, help="Symbols like ETHUSDT SOLUSDT BNBUSDT DOGEUSDT")
    ap.add_argument("--start", required=False, default=None, help="Start date (YYYY-MM-DD) UTC")
    ap.add_argument("--end", required=False, default=None, help="End date (YYYY-MM-DD) UTC (inclusive)")
    ap.add_argument("--tf", default="1m", choices=["1m","3m","5m","15m","30m","1h","4h","1d"], help="Kline interval")
    ap.add_argument("--market", default="futures", choices=["futures","spot"], help="Use Binance Futures or Spot")
    ap.add_argument("--outdir", default="data_dl", help="Output directory")
    ap.add_argument("--no-continuous", action="store_true", help="Futures only: use /fapi/v1/klines (symbol) instead of continuousKlines (pair)")
    ap.add_argument("--last-months", type=int, help="If set, download only the last N full months from now")
    ap.add_argument("--preset-last3", action="store_true", help="Use a preset list of symbols from the project and download the last 3 full months")
    args = ap.parse_args()

    # --- default convenience: if no symbols/dates passed, fetch BTCUSDT 1m for last 12 full months ---
    if not any([args.preset_last3, args.symbols, args.start, args.end, args.last_months]):
        args.symbols = ["BTCUSDT"]
        args.tf = "1m"
        args.market = "futures"
        args.last_months = 12
        print("[defaults] No args provided -> BTCUSDT 1m futures, last 12 full months")

    # Preset list: BTC, ETH, BNB, BCH, DOGE, 1INCH, AAVE, ADA, APE, AXS, DOT, SOL, XRP, LTC,
    # MATIC, AVAX, LINK, TRX, ATOM, UNI, XLM, ALGO, ICP, FIL, ETC, APT, NEAR, FTM, OPU->OP,
    # ARB, LDO, THETA, MANA, SAND, AXS (dedup), GRT, MKR, COMP, CRV, SNX, KSM, RUNE, FLOW,
    # EGLD, ZEC, DASH, KAVA, BAT
    if args.preset_last3:
        preset = [
            "BTC", "ETH", "BNB", "BCH", "1INCH", "AAVE", "ADA", "APE", "AXS",
            "DOT", "SOL", "XRP", "LTC", "AVAX", "LINK", "TRX", "ATOM", "UNI",
            "XLM", "ALGO", "ICP", "FIL", "ETC", "APT", "NEAR", "FTM", "OPU", "ARB",
            "LDO", "THETA", "MANA", "SAND", "AXS", "GRT", "MKR", "COMP", "CRV", "SNX",
            "KSM", "RUNE", "FLOW", "EGLD", "ZEC", "DASH", "KAVA", "BAT", "ENA"
        ]
        # Deduplicate while preserving order
        seen_p = set(); preset_norm = []
        for s in preset:
            if s not in seen_p:
                seen_p.add(s); preset_norm.append(s)
        args.symbols = preset_norm
        # Force last 3 full months
        if args.last_months is None:
            args.last_months = 3

    if args.last_months is None and (args.start is None or args.end is None):
        # If not already set by defaults above, make it last 12 months for convenience
        args.last_months = 12
        print("[defaults] Using last 12 full months (no --start/--end provided)")

    # Normalize symbols: uppercase, append USDT if missing, replace 'OPU' with 'OPUSDT', remove duplicates preserving order
    if args.symbols is None:
        args.symbols = []
    normalized = []
    seen = set()
    for sym in args.symbols:
        sym_up = sym.upper()
        if sym_up == "OPU":
            sym_up = "OPUSDT"
        elif not sym_up.endswith("USDT"):
            sym_up = sym_up + "USDT"
        if sym_up not in seen:
            seen.add(sym_up)
            normalized.append(sym_up)
    args.symbols = normalized

    if args.last_months is not None:
        # Calculate start and end dates for last N full months from today UTC
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        # end is last day of previous month (full month)
        end_year = today.year
        end_month = today.month - 1
        if end_month == 0:
            end_month = 12
            end_year -= 1
        last_day = calendar.monthrange(end_year, end_month)[1]
        end_date = datetime(end_year, end_month, last_day, tzinfo=timezone.utc)
        # start is first day of (N months ago)
        start_month = end_month - (args.last_months - 1)
        start_year = end_year
        while start_month <= 0:
            start_month += 12
            start_year -= 1
        start_date = datetime(start_year, start_month, 1, tzinfo=timezone.utc)
        args.start = start_date.strftime("%Y-%m-%d")
        args.end = end_date.strftime("%Y-%m-%d")

    outdir = Path(args.outdir)
    run(args.symbols, args.tf, args.market, args.start, args.end, outdir, use_continuous=(not args.no_continuous))

if __name__ == "__main__":
    main()

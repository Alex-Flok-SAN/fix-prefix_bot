#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Binance M1 Exporter (Streaming, Max-Load)
- Пишет по месяцам СРАЗУ после выгрузки каждого месяца (видно прогресс).
- Безопасно к лимитам биржи, но по умолчанию быстрее: sleep-ms=120.
- Поддержка spot / USDT-M futures.
- Резюмирование: если файл месяца уже существует и покрывает диапазон — пропускаем месяц.

Запуск:
  python binance_m1_export_streaming.py --symbol BTCUSDT --market futures \
    --start 2024-01-01 --end 2024-03-31 --out-dir data/history/BTCUSDT --sleep-ms 120
"""

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone, timedelta
from typing import List, Tuple

import pandas as pd
import requests
from dateutil import parser as dtparser

BINANCE_SPOT_URL = "https://api.binance.com/api/v3/klines"
BINANCE_FUTURES_URL = "https://fapi.binance.com/fapi/v1/klines"
ONE_MINUTE_MS = 60_000
MAX_LIMIT = 1000


def parse_time_to_ms(value) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    v = str(value).strip()
    if v.isdigit():
        return int(v)
    dt = dtparser.parse(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return int(dt.timestamp() * 1000)


def month_bounds_utc(ts_ms_start: int, ts_ms_end: int) -> List[Tuple[int, int, str]]:
    """Разбить [start; end] на месяцы UTC, вернуть список (m_start_ms, m_end_ms, 'YYYY-MM')."""
    start = datetime.utcfromtimestamp(ts_ms_start/1000).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_dt = datetime.utcfromtimestamp(ts_ms_end/1000)
    months = []
    cur = start
    while cur <= end_dt:
        # конец месяца
        if cur.month == 12:
            nxt = cur.replace(year=cur.year+1, month=1)
        else:
            nxt = cur.replace(month=cur.month+1)
        m_start = max(int(cur.replace(tzinfo=timezone.utc).timestamp()*1000), ts_ms_start)
        m_end = min(int((nxt.replace(tzinfo=timezone.utc) - timedelta(milliseconds=ONE_MINUTE_MS)).timestamp()*1000), ts_ms_end)
        months.append((m_start, m_end, cur.strftime("%Y-%m")))
        cur = nxt
    return months


def base_url(market: str) -> str:
    if market.lower() == "spot":
        return BINANCE_SPOT_URL
    if market.lower() == "futures":
        return BINANCE_FUTURES_URL
    raise ValueError("market must be 'spot' or 'futures'")


def http_get(url: str, params: dict, timeout: int) -> requests.Response:
    backoff = 0.4
    for _ in range(7):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r
            if r.status_code in (418, 403):
                raise RuntimeError(f"HTTP {r.status_code}: access denied / banned")
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(backoff); backoff *= 1.6; continue
            r.raise_for_status()
            return r
        except Exception as e:
            last = e
            time.sleep(backoff); backoff *= 1.6
    raise last


def fetch_seq(symbol: str, market: str, start_ms: int, end_ms: int, sleep_ms: int, timeout_s: int, verbose: bool) -> List[list]:
    url = base_url(market)
    all_rows = []
    cursor = start_ms
    while cursor <= end_ms:
        params = {"symbol": symbol.upper(), "interval": "1m", "startTime": cursor, "limit": MAX_LIMIT}
        resp = http_get(url, params, timeout_s)
        rows = resp.json()
        if not isinstance(rows, list) or not rows:
            break
        rows = [r for r in rows if isinstance(r, list) and len(r) >= 11 and r[0] <= end_ms]
        if not rows:
            break
        all_rows.extend(rows)
        last_open = rows[-1][0]
        cursor = last_open + ONE_MINUTE_MS
        if verbose:
            print(f"[fetch] +{len(rows)} (up to {datetime.utcfromtimestamp(last_open/1000)} UTC)")
        time.sleep(sleep_ms/1000.0)
    return all_rows


def rows_to_df(rows: List[list], symbol: str, market: str) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=[
            "ts_open_ms","open","high","low","close","volume",
            "quote_volume","trades","taker_buy_base","taker_buy_quote",
            "exchange","symbol","market"
        ])
    df = pd.DataFrame(rows, columns=[
        "open_time","open","high","low","close","volume","close_time",
        "quote_volume","trades","taker_buy_base","taker_buy_quote","ignore"
    ])
    df = df[["open_time","open","high","low","close","volume","quote_volume","trades","taker_buy_base","taker_buy_quote"]].copy()
    df["ts_open_ms"] = df["open_time"].astype("int64"); df.drop(columns=["open_time"], inplace=True)
    for c in ["open","high","low","close","volume","quote_volume","taker_buy_base","taker_buy_quote"]:
        df[c] = df[c].astype("float64")
    df["trades"] = df["trades"].astype("int64")
    df["exchange"] = "binance"; df["symbol"] = symbol.upper(); df["market"] = market.lower()
    df = df[[
        "ts_open_ms","open","high","low","close","volume",
        "quote_volume","trades","taker_buy_base","taker_buy_quote",
        "exchange","symbol","market"
    ]].sort_values("ts_open_ms").drop_duplicates(subset=["ts_open_ms"], keep="last").reset_index(drop=True)
    # базовые инварианты
    min_oc = df[["open","close"]].min(axis=1); max_oc = df[["open","close"]].max(axis=1)
    mask_ok = (df["low"] <= min_oc) & (df["high"] >= max_oc)
    if (~mask_ok).any():
        bad = (~mask_ok).sum()
        print(f"[warn] dropping {bad} rows with bad OHLC bounds")
        df = df[mask_ok].copy()
    return df


def ensure_continuity(df: pd.DataFrame, start_ms: int, end_ms: int, symbol: str, market: str,
                      sleep_ms: int, timeout_s: int, verbose: bool) -> pd.DataFrame:
    def find_gaps(ts: pd.Series):
        diffs = ts.diff().fillna(ONE_MINUTE_MS).astype("int64")
        gaps = []
        idx = diffs[diffs != ONE_MINUTE_MS].index
        for i in idx:
            prev_ts = int(ts.loc[i-1]) if i > 0 else int(ts.loc[i])
            cur_ts = int(ts.loc[i])
            if cur_ts - prev_ts > ONE_MINUTE_MS:
                gaps.append((prev_ts + ONE_MINUTE_MS, cur_ts - ONE_MINUTE_MS))
        return gaps

    for pass_i in range(2):
        ts = df["ts_open_ms"].astype("int64")
        gaps = find_gaps(ts)
        if not gaps:
            break
        if verbose:
            print(f"[continuity] pass {pass_i+1}: {len(gaps)} gap(s)")
        fill_rows = []
        for a,b in gaps:
            if verbose:
                print(f"[continuity] backfill {datetime.utcfromtimestamp(a/1000)}..{datetime.utcfromtimestamp(b/1000)}")
            chunk = fetch_seq(symbol, market, a, b, sleep_ms, timeout_s, verbose=False)
            fill_rows.extend(chunk)
        if fill_rows:
            add_df = rows_to_df(fill_rows, symbol, market)
            df = pd.concat([df, add_df], ignore_index=True).sort_values("ts_open_ms").drop_duplicates(subset=["ts_open_ms"], keep="last").reset_index(drop=True)
        else:
            break
    # финальные рамки
    df = df[(df["ts_open_ms"] >= start_ms) & (df["ts_open_ms"] <= end_ms)].copy()
    return df


def write_month(df: pd.DataFrame, out_dir: str, symbol: str, market: str, month_tag: str):
    os.makedirs(out_dir, exist_ok=True)
    fname = f"{symbol.upper()}_M1_{month_tag}.parquet"
    fpath = os.path.join(out_dir, fname)
    if df.empty:
        print(f"[write] skip {fname}: empty")
        return
    df.to_parquet(fpath, index=False, compression="snappy")
    # sha256
    h = hashlib.sha256()
    with open(fpath, "rb") as f:
        while True:
            chunk = f.read(1024*1024)
            if not chunk: break
            h.update(chunk)
    digest = h.hexdigest()
    manifest = {
        "symbol": symbol.upper(),
        "market": market.lower(),
        "interval": "1m",
        "month": month_tag,
        "rows": int(len(df)),
        "ts_min_ms": int(df["ts_open_ms"].min()),
        "ts_max_ms": int(df["ts_open_ms"].max()),
        "file": fname,
        "sha256": digest,
    }
    mpath = os.path.join(out_dir, f"{symbol.upper()}_M1_{month_tag}.manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[write] {fname} rows={len(df)} ts=[{manifest['ts_min_ms']}..{manifest['ts_max_ms']}] sha256={digest[:12]}…")


def month_already_complete(out_dir: str, symbol: str, month_tag: str) -> bool:
    fpath = os.path.join(out_dir, f"{symbol.upper()}_M1_{month_tag}.parquet")
    mpath = os.path.join(out_dir, f"{symbol.upper()}_M1_{month_tag}.manifest.json")
    return os.path.exists(fpath) and os.path.exists(mpath)


def main():
    ap = argparse.ArgumentParser(description="Binance M1 exporter (streaming by month)")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--market", choices=["spot","futures"], default="spot")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--sleep-ms", type=int, default=120)
    ap.add_argument("--timeout-s", type=int, default=20)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    symbol = args.symbol.upper()
    market = args.market.lower()
    start_ms = parse_time_to_ms(args.start)
    end_ms = parse_time_to_ms(args.end)
    if end_ms < start_ms:
        raise SystemExit("end < start")

    months = month_bounds_utc(start_ms, end_ms)
    print(f"[run] {symbol} {market} {datetime.utcfromtimestamp(start_ms/1000)}..{datetime.utcfromtimestamp(end_ms/1000)} UTC ({len(months)} month(s))")
    os.makedirs(args.out_dir, exist_ok=True)

    for m_start, m_end, tag in months:
        # если уже есть — пропускаем (резюмирование)
        if month_already_complete(args.out_dir, symbol, tag):
            print(f"[skip] {tag} already exported")
            continue
        print(f"[month] {tag}: fetching…")
        rows = fetch_seq(symbol, market, m_start, m_end, args.sleep_ms, args.timeout_s, verbose=not args.quiet)
        df = rows_to_df(rows, symbol, market)
        print(f"[df] {tag}: rows={len(df)}")
        df = ensure_continuity(df, m_start, m_end, symbol, market, args.sleep_ms, args.timeout_s, verbose=not args.quiet)
        # фильтр ровно по месяцу
        df = df[(df['ts_open_ms'] >= m_start) & (df['ts_open_ms'] <= m_end)].copy()
        write_month(df, args.out_dir, symbol, market, tag)

    print("[done] export completed")
    

if __name__ == "__main__":
    main()

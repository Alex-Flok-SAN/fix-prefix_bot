#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Binance M1 Exporter — выгрузка минутных свечей в Parquet по месяцам.

- Источник: Binance Spot или USDT-M Futures
- Интервал: 1m (минутки)
- Таймстемпы: int (миллисекунды) UTC
- Файлы: {SYMBOL}_M1_{YYYY-MM}.parquet + {YYYY-MM}.manifest.json (hash/rows/ts-range)

Запуск:
    python binance_m1_export.py --symbol BTCUSDT --market spot --start 2024-01-01 --end 2024-03-31 --out-dir ./data/binance_spot/BTCUSDT

Зависимости: см. requirements.txt
"""

import argparse
import hashlib
import io
import os
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Tuple

import pandas as pd
import requests
from dateutil import parser as dtparser

BINANCE_SPOT_URL = "https://api.binance.com/api/v3/klines"
BINANCE_FUTURES_URL = "https://fapi.binance.com/fapi/v1/klines"
ONE_MINUTE_MS = 60_000
MAX_LIMIT = 1000


@dataclass
class ExportConfig:
    symbol: str
    market: str  # 'spot' or 'futures'
    start_ms: int
    end_ms: int
    out_dir: str
    sleep_ms: int = 200
    timeout_s: int = 15
    verbose: bool = True


def parse_time_to_ms(value: str) -> int:
    """Принимает ISO8601 ('2024-01-01 00:00:00') или миллисекунды (строка/число), возвращает int ms (UTC)."""
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


def base_url(market: str) -> str:
    m = market.lower()
    if m == "spot":
        return BINANCE_SPOT_URL
    if m == "futures":
        return BINANCE_FUTURES_URL
    raise ValueError("market must be 'spot' or 'futures'")


def polite_sleep(ms: int) -> None:
    time.sleep(ms / 1000.0)


def http_get(url: str, params: dict, timeout: int) -> requests.Response:
    """GET с простым ретраем и экспоненциальной задержкой на 429/5xx."""
    backoff = 0.5
    attempts = 6
    last_exc = None
    for i in range(attempts):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp
            # 418/403 — заблокировано; 429 — лимиты; 5xx — временно
            if resp.status_code in (418, 403):
                raise RuntimeError(f"HTTP {resp.status_code}: access denied / banned by Binance")
            # Лимиты/временные сбои — подождать и повторить
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(backoff)
                backoff *= 1.5
                continue
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_exc = e
            time.sleep(backoff)
            backoff *= 1.5
    # Если сюда дошли — всё плохо
    if last_exc:
        raise last_exc
    raise RuntimeError("Unknown HTTP error")


def fetch_klines_seq(symbol: str, market: str, start_ms: int, end_ms: int, sleep_ms: int, timeout_s: int, verbose: bool) -> List[list]:
    """
    Последовательный сбор минуток: запрашиваем пачками по 1000 свечей, сдвигаем startTime вперёд.
    Гарантирует монотонный рост openTime в данных. Возвращает список массивов (как у Binance).
    """
    url = base_url(market)
    s = requests.Session()
    all_rows: List[list] = []
    cursor = start_ms
    if verbose:
        print(f"[fetch] {symbol} {market} {datetime.utcfromtimestamp(start_ms/1000)}..{datetime.utcfromtimestamp(end_ms/1000)} UTC")
    while cursor <= end_ms:
        params = {
            "symbol": symbol.upper(),
            "interval": "1m",
            "startTime": cursor,
            "limit": MAX_LIMIT,
        }
        resp = http_get(url, params, timeout_s)
        rows = resp.json()
        if not isinstance(rows, list):
            raise RuntimeError(f"Unexpected response: {rows}")
        if not rows:
            # Нет данных — вероятно, конец диапазона
            break
        # Фильтруем только то, что не превышает end_ms
        rows = [r for r in rows if isinstance(r, list) and len(r) >= 11 and r[0] <= end_ms]
        if not rows:
            break
        all_rows.extend(rows)
        last_open_ms = rows[-1][0]
        # Следующий курсор — +1 минута
        cursor = last_open_ms + ONE_MINUTE_MS
        if verbose:
            print(f"[fetch] got {len(rows)} rows, last_open={datetime.utcfromtimestamp(last_open_ms/1000)} UTC")
        polite_sleep(sleep_ms)
    return all_rows


def rows_to_dataframe(rows: List[list], symbol: str, market: str) -> pd.DataFrame:
    """Преобразует сырой ответ Binance в DataFrame с нужными колонками и типами."""
    if not rows:
        return pd.DataFrame(columns=[
            "ts_open_ms", "open", "high", "low", "close", "volume",
            "quote_volume", "trades", "taker_buy_base", "taker_buy_quote",
            "exchange", "symbol", "market"
        ])
    df = pd.DataFrame(rows, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    df = df[["open_time", "open", "high", "low", "close", "volume", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote"]].copy()
    # Каст типов
    df["ts_open_ms"] = df["open_time"].astype("int64")
    df.drop(columns=["open_time"], inplace=True)
    float_cols = ["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_base", "taker_buy_quote"]
    int_cols = ["trades"]
    for c in float_cols:
        df[c] = df[c].astype("float64")
    df["trades"] = df["trades"].astype("int64")
    df["exchange"] = "binance"
    df["symbol"] = symbol.upper()
    df["market"] = market.lower()
    # Упорядочить колонки
    df = df[[
        "ts_open_ms", "open", "high", "low", "close", "volume",
        "quote_volume", "trades", "taker_buy_base", "taker_buy_quote",
        "exchange", "symbol", "market"
    ]]
    # Сортировка и дедуп
    df = df.sort_values("ts_open_ms").drop_duplicates(subset=["ts_open_ms"], keep="last").reset_index(drop=True)
    # Базовые инварианты цены
    min_oc = df[["open", "close"]].min(axis=1)
    max_oc = df[["open", "close"]].max(axis=1)
    bad_low = (df["low"] > min_oc)
    bad_high = (df["high"] < max_oc)
    if bad_low.any() or bad_high.any():
        # Фильтруем заведомый мусор и предупреждаем
        n_bad = int(bad_low.sum() + bad_high.sum())
        print(f"[warn] filtered {n_bad} rows with inconsistent OHLC bounds")
        df = df[~(bad_low | bad_high)].copy()
    return df


def ensure_continuity(df: pd.DataFrame, start_ms: int, end_ms: int, symbol: str, market: str,
                      sleep_ms: int, timeout_s: int, verbose: bool) -> pd.DataFrame:
    """
    Проверяет шаг ровно 60_000, при дырках — пытается дозагрузить недостающие интервалы.
    Повторяет до 2 проходов дозагрузки.
    """
    def find_gaps(ts: pd.Series) -> List[Tuple[int, int]]:
        diffs = ts.diff().fillna(ONE_MINUTE_MS).astype("int64")
        gap_idx = diffs[diffs != ONE_MINUTE_MS].index
        gaps: List[Tuple[int, int]] = []
        for i in gap_idx:
            prev_ts = int(ts.loc[i - 1]) if i > 0 else int(ts.loc[i])
            curr_ts = int(ts.loc[i])
            if curr_ts - prev_ts > ONE_MINUTE_MS:
                gaps.append((prev_ts + ONE_MINUTE_MS, curr_ts - ONE_MINUTE_MS))
        return gaps

    for pass_i in range(2):
        ts = df["ts_open_ms"].astype("int64")
        gaps = find_gaps(ts)
        if not gaps:
            return df
        if verbose:
            print(f"[continuity] pass {pass_i+1}: found {len(gaps)} gap(s)")
        # Догружаем каждую дыру
        fill_rows = []
        for a, b in gaps:
            if verbose:
                print(f"[continuity] backfilling {datetime.utcfromtimestamp(a/1000)}..{datetime.utcfromtimestamp(b/1000)} UTC")
            chunk = fetch_klines_seq(symbol, market, a, b, sleep_ms, timeout_s, verbose=False)
            fill_rows.extend(chunk)
        if fill_rows:
            add_df = rows_to_dataframe(fill_rows, symbol, market)
            df = pd.concat([df, add_df], ignore_index=True)
            df = df.sort_values("ts_open_ms").drop_duplicates(subset=["ts_open_ms"], keep="last").reset_index(drop=True)
        else:
            break
    # Финальная проверка
    ts = df["ts_open_ms"].astype("int64")
    diffs = ts.diff().fillna(ONE_MINUTE_MS).astype("int64")
    n_bad = int((diffs != ONE_MINUTE_MS).sum())
    if n_bad > 0:
        print(f"[warn] still {n_bad} discontinuities remain (биржевые простои возможны)")
    # Обрежем по точным границам [start_ms, end_ms]
    df = df[(df["ts_open_ms"] >= start_ms) & (df["ts_open_ms"] <= end_ms)].copy()
    return df


def write_monthly_parquets(df: pd.DataFrame, out_dir: str, symbol: str, market: str) -> None:
    """Разбивает DF по месяцам и пишет Parquet + manifest c sha256."""
    if df.empty:
        print("[write] nothing to write (empty dataframe)")
        return
    os.makedirs(out_dir, exist_ok=True)
    dt = pd.to_datetime(df["ts_open_ms"], unit="ms", utc=True)
    months = dt.dt.to_period("M").astype(str)
    df = df.copy()
    df["__month__"] = months

    for month, g in df.groupby("__month__", sort=True):
        g2 = g.drop(columns=["__month__"])
        fname = f"{symbol.upper()}_M1_{month}.parquet"
        fpath = os.path.join(out_dir, fname)
        g2.to_parquet(fpath, index=False, compression="snappy")
        # sha256
        h = hashlib.sha256()
        with open(fpath, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        digest = h.hexdigest()
        manifest = {
            "symbol": symbol.upper(),
            "market": market.lower(),
            "interval": "1m",
            "month": month,
            "rows": int(len(g2)),
            "ts_min_ms": int(g2["ts_open_ms"].min()),
            "ts_max_ms": int(g2["ts_open_ms"].max()),
            "file": fname,
            "sha256": digest,
        }
        mpath = os.path.join(out_dir, f"{symbol.upper()}_M1_{month}.manifest.json")
        with open(mpath, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        print(f"[write] {fname} rows={len(g2)} ts=[{manifest['ts_min_ms']}..{manifest['ts_max_ms']}] sha256={digest[:12]}…")


def main():
    ap = argparse.ArgumentParser(description="Binance M1 exporter → Parquet per month")
    ap.add_argument("--symbol", required=True, help="Например: BTCUSDT")
    ap.add_argument("--market", choices=["spot", "futures"], default="spot", help="Рынок: spot или futures (USDT-M)")
    ap.add_argument("--start", required=True, help="Начало диапазона (ISO или миллисекунды UTC)")
    ap.add_argument("--end", required=True, help="Конец диапазона (ISO или миллисекунды UTC)")
    ap.add_argument("--out-dir", required=True, help="Папка для выгрузки (будет создана)")
    ap.add_argument("--sleep-ms", type=int, default=200, help="Пауза между HTTP-запросами (мс)")
    ap.add_argument("--timeout-s", type=int, default=15, help="Таймаут запроса (сек)")
    ap.add_argument("--quiet", action="store_true", help="Тише логов")
    args = ap.parse_args()

    symbol = args.symbol.upper()
    market = args.market.lower()
    start_ms = parse_time_to_ms(args.start)
    end_ms = parse_time_to_ms(args.end)
    if end_ms < start_ms:
        raise SystemExit("end < start")
    cfg = ExportConfig(
        symbol=symbol,
        market=market,
        start_ms=start_ms,
        end_ms=end_ms,
        out_dir=args.out_dir,
        sleep_ms=args.sleep_ms,
        timeout_s=args.timeout_s,
        verbose=not args.quiet,
    )

    rows = fetch_klines_seq(cfg.symbol, cfg.market, cfg.start_ms, cfg.end_ms, cfg.sleep_ms, cfg.timeout_s, cfg.verbose)
    df = rows_to_dataframe(rows, cfg.symbol, cfg.market)
    if cfg.verbose:
        print(f"[df] rows: {len(df)} unique minutes [{cfg.start_ms}..{cfg.end_ms}]")

    df = ensure_continuity(df, cfg.start_ms, cfg.end_ms, cfg.symbol, cfg.market, cfg.sleep_ms, cfg.timeout_s, cfg.verbose)
    write_monthly_parquets(df, cfg.out_dir, cfg.symbol, cfg.market)
    print("[done] export completed")


if __name__ == "__main__":
    main()

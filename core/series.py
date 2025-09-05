"""
core.series
-----------
Загрузка локальных минуток (CSV/Parquet) и ресемплинг в более крупные ТФ.

Форматы файлов (ожидаемые столбцы):
  - CSV:    ts_open_ms,open,high,low,close,volume,ts_close_ms
  - Parquet с теми же полями

Имена файлов:
  {SYMBOL}_M1_YYYY-MM.csv
  {SYMBOL}_M1_YYYY-MM.parquet

Основные функции:
  - load_nearby_1m(symbol, center_dt, back_n=5000, fwd_n=5000, data_dir="data_1m")
  - resample(candles_1m, tf_minutes)

Обе функции не зависят от UI и могут использоваться из любого места ядра.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Iterable, Tuple
import os
import glob
import math
from datetime import datetime, timezone
import json

# --- Опциональные зависимости ---
try:
    import pandas as pd  # type: ignore
except Exception:
    pd = None

# --- Типы (если есть core.types — используем его, иначе локальные датаклассы) ---
try:
    from .types import Candle  # type: ignore
except Exception:
    @dataclass
    class Candle:
        ts: int  # ms since epoch
        o: float
        h: float
        l: float
        c: float
        v: float = 0.0


# ---------- Утилиты времени ----------

def as_ms(ts_or_str: int | float | str) -> int:
    """Преобразовать вход (ms, seconds, или строку) в миллисекунды UTC."""
    if isinstance(ts_or_str, (int,)):
        # считаем, что это уже ms (большие числа)
        return int(ts_or_str)
    if isinstance(ts_or_str, float):
        # вероятно seconds
        return int(round(ts_or_str * 1000))
    # строка времени
    s = ts_or_str.strip()
    # Попытки: "YYYY-MM-DD HH:MM", "YYYY-MM-DDTHH:MM", "YYYY-MM-DD"
    fmts = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except Exception:
            pass
    # последний шанс — попробовать распарсить как ISO
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        raise ValueError(f"Unsupported datetime format: {ts_or_str!r}")


def floor_bucket_ms(ts_ms: int, tf_minutes: int) -> int:
    """Округлить таймстамп вниз до начала свечи указанного ТФ (в мс)."""
    tf_ms = tf_minutes * 60_000
    return (ts_ms // tf_ms) * tf_ms


# ---------- Работа с локальными файлами ----------

def _list_data_files(symbol: str, data_dir: str) -> List[str]:
    """Все CSV/Parquet для символа в каталоге."""
    patt_csv = os.path.join(data_dir, f"{symbol}_M1_*.csv")
    patt_parq = os.path.join(data_dir, f"{symbol}_M1_*.parquet")
    files = sorted(glob.glob(patt_csv)) + sorted(glob.glob(patt_parq))
    return files


def _read_csv_safe(path: str) -> Optional[List[Candle]]:
    """Прочитать CSV, вернуть список Candle или None при ошибке."""
    try:
        if pd is None:
            # Фоллбэк без pandas: минимальный CSV-парсер
            import csv
            out: List[Candle] = []
            with open(path, "r", newline="") as f:
                dr = csv.DictReader(f)
                for row in dr:
                    ts = int(row["ts_open_ms"])
                    o = float(row["open"]); h = float(row["high"])
                    l = float(row["low"]);  c = float(row["close"])
                    v = float(row.get("volume", 0.0) or 0.0)
                    out.append(Candle(ts, o, h, l, c, v))
            return out
        # Pandas путь
        try:
            df = pd.read_csv(path, engine="c")
        except Exception:
            # engine='python' — но без low_memory
            df = pd.read_csv(path, engine="python")
        # нормализуем имена
        cols = {c.lower(): c for c in df.columns}
        need = ["ts_open_ms", "open", "high", "low", "close"]
        for n in need:
            if n not in cols:
                # попробуем без нижнего подчеркивания (на всякий случай)
                if n.replace("_", "") in cols:
                    cols[n] = cols[n.replace("_", "")]
                else:
                    return None
        ts_col = cols["ts_open_ms"]
        out: List[Candle] = []
        for r in df.itertuples(index=False):
            # быстрый доступ по индексу столбцов
            row = r._asdict() if hasattr(r, "_asdict") else {k: getattr(r, k) for k in df.columns}
            ts = int(row[ts_col])
            o = float(row[cols["open"]]); h = float(row[cols["high"]])
            l = float(row[cols["low"]]);  c = float(row[cols["close"]])
            v = float(row.get("volume", 0.0) or 0.0)
            out.append(Candle(ts, o, h, l, c, v))
        return out
    except Exception:
        return None


def _read_parquet_safe(path: str) -> Optional[List[Candle]]:
    """Прочитать Parquet, вернуть список Candle или None при ошибке."""
    if pd is None:
        return None
    try:
        df = pd.read_parquet(path)
        cols = {c.lower(): c for c in df.columns}
        need = ["ts_open_ms", "open", "high", "low", "close"]
        for n in need:
            if n not in cols:
                return None
        ts_col = cols["ts_open_ms"]
        out: List[Candle] = []
        for r in df.itertuples(index=False):
            row = r._asdict() if hasattr(r, "_asdict") else {k: getattr(r, k) for k in df.columns}
            ts = int(row[ts_col])
            o = float(row[cols["open"]]); h = float(row[cols["high"]])
            l = float(row[cols["low"]]);  c = float(row[cols["close"]])
            v = float(row.get("volume", 0.0) or 0.0)
            out.append(Candle(ts, o, h, l, c, v))
        return out
    except Exception:
        return None


def _load_month(path_csv: str, path_parquet: str) -> List[Candle]:
    """
    Загрузить один месяц: пробуем CSV, затем Parquet.
    Возвращаем отсортированный список Candle (по ts).
    """
    rows: Optional[List[Candle]] = None
    if os.path.exists(path_csv):
        rows = _read_csv_safe(path_csv)
    if rows is None and os.path.exists(path_parquet):
        rows = _read_parquet_safe(path_parquet)
    return sorted(rows or [], key=lambda x: x.ts)


def load_nearby_1m(
    symbol: str,
    center_dt: int | float | str,
    back_n: int = 5000,
    fwd_n: int = 5000,
    data_dir: str = "data_1m",
) -> List[Candle]:
    """
    Загрузить вокруг центра (center_dt) минутные бары из локальной базы.
    Ищет только в релевантных месяцах.

    center_dt: ms/seconds/string — центр окна
    back_n/fwd_n: сколько минут слева/справа приблизительно (для ограничения месяцов)
    """
    center_ms = as_ms(center_dt)
    # Примерная вилка по датам (с запасом)
    total_minutes = max(back_n + fwd_n, 1)
    total_ms = total_minutes * 60_000
    left_ms = center_ms - total_ms
    right_ms = center_ms + total_ms

    # Список файлов только по нужным месяцам
    files = _list_data_files(symbol, data_dir)
    if not files:
        return []

    # Выберем только месяцы, которые пересекают диапазон [left_ms, right_ms] по имени файла
    # Имя формата: SYMBOL_M1_YYYY-MM.ext
    def month_key(p: str) -> Tuple[int, int]:
        base = os.path.basename(p)
        # ищем YYYY-MM в имени
        ym = None
        for part in base.split("_"):
            if len(part) == 7 and part[4] == "-":
                ym = part
                break
        if ym is None:
            return (0, 0)
        y, m = ym.split("-")
        try:
            return (int(y), int(m))
        except Exception:
            return (0, 0)

    # Сгруппируем по месяцу: csv и parquet
    by_month = {}
    for p in files:
        y, m = month_key(p)
        if (y, m) == (0, 0):
            continue
        by_month.setdefault((y, m), {"csv": None, "parquet": None})
        if p.endswith(".csv"):
            by_month[(y, m)]["csv"] = p
        elif p.endswith(".parquet"):
            by_month[(y, m)]["parquet"] = p

    # Оставим месяцы в диапазоне [left_ms, right_ms] с небольшим запасом (±1 месяц)
    def month_start_ms(y: int, m: int) -> int:
        dt = datetime(y, m, 1, tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)

    def next_month(y: int, m: int) -> Tuple[int, int]:
        return (y + (m // 12), 1 if m == 12 else m + 1)

    def month_end_ms(y: int, m: int) -> int:
        ny, nm = next_month(y, m)
        dt = datetime(ny, nm, 1, tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000) - 1

    wanted_months = []
    for (y, m), paths in sorted(by_month.items()):
        ms0 = month_start_ms(y, m)
        ms1 = month_end_ms(y, m)
        if ms1 < left_ms or ms0 > right_ms:
            # вне диапазона — пропускаем
            continue
        wanted_months.append(((y, m), paths))

    # Загрузка
    out: List[Candle] = []
    for (y, m), paths in wanted_months:
        rows = _load_month(paths.get("csv") or "", paths.get("parquet") or "")
        if rows:
            out.extend(rows)

    # Отфильтровать точнее по диапазону
    if not out:
        return []
    out.sort(key=lambda x: x.ts)
    # Уточним “окно” (берём немного больше, чтобы при ресемплинге хватало границ)
    pad_ms = 60 * 60_000  # +1 час
    left = left_ms - pad_ms
    right = right_ms + pad_ms
    out = [c for c in out if left <= c.ts <= right]
    return out


# ---------- Ресемплинг ----------

def resample(candles_1m: Iterable[Candle], tf_minutes: int) -> List[Candle]:
    """
    Ресемплинг минутных баров в более крупный ТФ.
    Возвращает список Candle с ts = началу свечи (UTC, ms).
    """
    tf_ms = tf_minutes * 60_000
    buckets: dict[int, dict] = {}

    for c in candles_1m:
        b = (c.ts // tf_ms) * tf_ms
        agg = buckets.get(b)
        if agg is None:
            buckets[b] = {
                "o": c.o,
                "h": c.h,
                "l": c.l,
                "c": c.c,
                "v": float(c.v or 0.0),
                "ts": b,
            }
        else:
            agg["h"] = max(agg["h"], c.h)
            agg["l"] = min(agg["l"], c.l)
            agg["c"] = c.c
            agg["v"] += float(c.v or 0.0)

    out = [Candle(ts=a["ts"], o=a["o"], h=a["h"], l=a["l"], c=a["c"], v=a["v"]) for a in buckets.values()]
    out.sort(key=lambda x: x.ts)
    return out

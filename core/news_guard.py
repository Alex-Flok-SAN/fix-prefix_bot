#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
news_guard.py — модуль фильтра новостей для FPF-бота.

Функции высокого уровня:
- is_in_news_window(ts_ms: int, symbols: list[str] | None = None) -> bool
    Возвращает True, если момент времени попадает в окно новости (±1 час) по важным событиям (FOMC, NFP, CPI).

- annotate_with_news(payload: dict) -> dict
    Добавляет к произвольному словарю аннотацию о ближайших новостях в окне ±1 часа от времени now или от payload["ts_ms"]
    (если задано). Полезно для подписей планов/сигналов.

Загрузка календаря:
- По умолчанию календарь пустой. Его можно пополнить:
  * программно через add_event(...)
  * загрузкой CSV/JSON из путей (см. load_from_csv/load_from_json)

CSV-формат (минимум):
  date,time,tz,category,title,importance
  2025-09-19,12:30,America/New_York,NFP,Nonfarm Payrolls,high
  2025-09-25,14:00,America/New_York,FOMC,Fed Interest Rate Decision,high
  2025-09-11,08:30,America/New_York,CPI,US CPI (YoY),high

Поддерживаются и колонки start_ts_ms,end_ts_ms (в мс). Если заданы —
они имеют приоритет. Если нет — вычисляем из date/time/tz с длительностью по умолчанию (60 минут).

Важно: модуль не ходит в интернет — источники календаря интегрируются извне.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Iterable, Dict, Tuple
from pathlib import Path
import json
import csv
import math
import time
from datetime import datetime, timedelta
import zoneinfo

# ==========================
# Модель события и календарь
# ==========================

@dataclass
class NewsEvent:
    start_ts_ms: int
    end_ts_ms: int
    category: str        # e.g. "FOMC", "NFP", "CPI"
    title: str
    importance: str = "high"  # high/medium/low
    symbols: Optional[List[str]] = None  # если None или ["*"], событие глобально для всех пар
    source: str = "manual"

    def window_with_buffer(self, pre_s: int = 3600, post_s: int = 3600) -> Tuple[int, int]:
        pre = self.start_ts_ms - pre_s * 1000
        post = self.end_ts_ms + post_s * 1000
        return pre, post

class NewsCalendar:
    def __init__(self):
        self._events: List[NewsEvent] = []
        # какие категории считаем важными по умолчанию
        self.important_categories = {"FOMC", "NFP", "CPI"}
        self.default_event_minutes = 60
        self.default_pre_s = 3600
        self.default_post_s = 3600

    # -------- CRUD ---------
    def clear(self):
        self._events.clear()

    def add_event(self, ev: NewsEvent):
        self._events.append(ev)

    def add(self, *, start_ts_ms: int, end_ts_ms: int, category: str, title: str,
            importance: str = "high", symbols: Optional[List[str]] = None, source: str = "manual"):
        self._events.append(NewsEvent(start_ts_ms, end_ts_ms, category, title, importance, symbols, source))

    # -------- Loading -------
    def load_from_json(self, path: str | Path):
        p = Path(path)
        if not p.exists():
            return
        data = json.loads(p.read_text(encoding="utf-8"))
        # Поддержка форматов: {events:[...] } или [ ... ]
        rows = data.get("events") if isinstance(data, dict) else data
        for r in rows or []:
            self._add_from_mapping(r)

    def load_from_csv(self, path: str | Path):
        p = Path(path)
        if not p.exists():
            return
        with p.open("r", encoding="utf-8", newline="") as f:
            rd = csv.DictReader(f)
            for r in rd:
                self._add_from_mapping(r)

    def _add_from_mapping(self, m: Dict):
        # Приоритет: start_ts_ms/end_ts_ms, иначе date+time(+tz)
        try:
            if "start_ts_ms" in m and "end_ts_ms" in m:
                start_ts_ms = int(m["start_ts_ms"])  # noqa
                end_ts_ms = int(m["end_ts_ms"])      # noqa
            else:
                dt_str = str(m.get("date", "")).strip()
                tm_str = str(m.get("time", "00:00")).strip()
                tz_str = str(m.get("tz", "UTC")).strip() or "UTC"
                cat = str(m.get("category", "")).upper().strip()
                title = str(m.get("title", cat)).strip()
                imp = str(m.get("importance", "high")).lower().strip() or "high"
                dur_min = int(m.get("duration_min", self.default_event_minutes))
                if not dt_str:
                    return
                # parse dt
                tz = zoneinfo.ZoneInfo(tz_str)
                dt = datetime.fromisoformat(f"{dt_str} {tm_str}")
                dt = dt.replace(tzinfo=tz)
                start_ts_ms = int(dt.timestamp() * 1000)
                end_ts_ms = start_ts_ms + dur_min * 60 * 1000
                symbols = m.get("symbols")
                if isinstance(symbols, str):
                    # e.g. "BTCUSDT;ETHUSDT" or "*"
                    symbols = None if symbols.strip() in ("", "*") else [s.strip() for s in symbols.split(";") if s.strip()]
                self.add(start_ts_ms=start_ts_ms, end_ts_ms=end_ts_ms, category=cat or "GENERIC",
                         title=title, importance=imp, symbols=symbols, source=str(m.get("source", "csv")))
                return
            # if we are here, timestamps were provided directly
            cat = str(m.get("category", "GENERIC")).upper()
            title = str(m.get("title", cat))
            imp = str(m.get("importance", "high")).lower()
            symbols = m.get("symbols")
            if isinstance(symbols, str):
                symbols = None if symbols.strip() in ("", "*") else [s.strip() for s in symbols.split(";") if s.strip()]
            self.add(start_ts_ms=start_ts_ms, end_ts_ms=end_ts_ms, category=cat,
                     title=title, importance=imp, symbols=symbols, source=str(m.get("source", "json")))
        except Exception:
            # пропускаем некорректную строку
            return

    # -------- Queries -------
    def is_in_window(self, ts_ms: int, symbols: Optional[Iterable[str]] = None,
                      categories: Optional[Iterable[str]] = None,
                      pre_s: Optional[int] = None, post_s: Optional[int] = None,
                      importance_min: str = "medium") -> bool:
        """True, если ts_ms попадает в окно (с буферами) важной новости.
        importance_min: минимальная важность для учёта (low/medium/high).
        """
        pre = self.default_pre_s if pre_s is None else int(pre_s)
        post = self.default_post_s if post_s is None else int(post_s)
        cats = set(categories) if categories else self.important_categories
        imp_rank = {"low": 0, "medium": 1, "high": 2}
        need = imp_rank.get(importance_min, 1)
        syms = None
        if symbols:
            syms = {s.upper() for s in symbols}

        for ev in self._events:
            if ev.category.upper() not in cats:
                continue
            if imp_rank.get(ev.importance, 0) < need:
                continue
            if syms and ev.symbols and ev.symbols != ["*"]:
                # событие относится к ограниченному набору символов
                if syms.isdisjoint({s.upper() for s in ev.symbols}):
                    continue
            w0, w1 = ev.window_with_buffer(pre, post)
            if w0 <= ts_ms <= w1:
                return True
        return False

    def nearby_events(self, ts_ms: int, horizon_s: int = 7200,
                      categories: Optional[Iterable[str]] = None) -> List[NewsEvent]:
        cats = set(categories) if categories else None
        out: List[NewsEvent] = []
        for ev in self._events:
            if cats and ev.category.upper() not in cats:
                continue
            if abs(ts_ms - ev.start_ts_ms) <= horizon_s * 1000 or abs(ts_ms - ev.end_ts_ms) <= horizon_s * 1000:
                out.append(ev)
        out.sort(key=lambda e: e.start_ts_ms)
        return out

# ==========================
# Глобальные функции / singleton
# ==========================

_calendar = NewsCalendar()

def calendar() -> NewsCalendar:
    return _calendar

# Основное API, которое используют планировщик/экзекьютор

def is_in_news_window(ts_ms: int, symbols: Optional[Iterable[str]] = None,
                      pre_s: int = 3600, post_s: int = 3600) -> bool:
    return _calendar.is_in_window(ts_ms, symbols=symbols, pre_s=pre_s, post_s=post_s)


def annotate_with_news(payload: Dict) -> Dict:
    """Помечает словарь сведениями о новостях рядом с ts_ms.
    Если в payload нет ts_ms — используем текущее время.
    """
    ts_ms = int(payload.get("ts_ms", int(time.time() * 1000)))
    events = _calendar.nearby_events(ts_ms, horizon_s=7200)  # ±2 часа
    if not events:
        return payload
    # компактная аннотация
    note = []
    for ev in events[:5]:
        note.append({
            "category": ev.category,
            "title": ev.title,
            "start_ts_ms": ev.start_ts_ms,
            "end_ts_ms": ev.end_ts_ms,
            "importance": ev.importance,
        })
    payload.setdefault("meta", {})["news"] = note
    return payload

# ==========================
# Утилиты загрузки по умолчанию
# ==========================

def load_default_us_calendar_if_exists(base_dir: str | Path = "data/news") -> None:
    """Пробует загрузить встроенный календарь из data/news: us_high.csv/json, если есть.
    Это может быть выгрузка FOMC/NFP/CPI, подготовленная оффлайн.
    """
    base = Path(base_dir)
    csv_path = base / "us_high.csv"
    json_path = base / "us_high.json"
    if csv_path.exists():
        _calendar.load_from_csv(csv_path)
    if json_path.exists():
        _calendar.load_from_json(json_path)

# Попробуем загрузить дефолт при импорте (если файл есть — хорошо; если нет — тишина)
try:
    load_default_us_calendar_if_exists()
except Exception:
    pass

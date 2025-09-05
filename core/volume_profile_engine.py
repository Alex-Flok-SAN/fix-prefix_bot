# core/volume_profile_engine.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Deque, Tuple, List, Optional
from collections import deque, defaultdict
import math
import time
import json
import hashlib

from .event_bus import EventBus

@dataclass
class ProfileParams:
    # бин по цене: либо фиксированный шаг (tick), либо доля от цены (pct)
    mode: str = "pct"           # "pct" | "tick"
    binsize_pct: float = 0.0007 # 0.07% от цены по умолчанию
    binsize_tick: float = 1.0   # если mode="tick"
    va_percent: float = 0.70    # доля объёма для value area

    # окна пересчёта
    daily_minutes: int = 24*60          # полный день
    session_minutes: int = 6*60         # скользящее окно для «сессии» (пример)
    publish_throttle_s: float = 5.0     # не публиковать чаще, чем раз в N секунд

    # дополнительные уровни и квантование
    add_round: bool = True                 # публиковать ROUND уровень (ближайший к VWAP)
    round_steps: Tuple[float, ...] = (5.0, 10.0, 50.0, 100.0)  # сетка округлений по умолчанию

class VolumeProfileEngine:
    """
    Считает профиль объёма по минуткам в двух окнах: daily и session.
    Публикует в bus 'levels.update' расширенные уровни: VWAP_D, POC_D, VAH/VAL_D и аналогично для session.
    Детектор ФПФ сможет видеть meta у уровней.
    """
    def _tick_for_symbol(self, symbol: str) -> float:
        # Бейзлайн-тики по популярным крипто; дефолт — 0.01
        return {
            "BTCUSDT": 0.5,
            "ETHUSDT": 0.05,
        }.get(symbol, 0.01)

    def _quantize_price(self, symbol: str, price: float) -> float:
        # Квантование цены для стабильности публикаций уровней
        tick = self._tick_for_symbol(symbol)
        if tick <= 0:
            tick = 0.01
        return round(price / tick) * tick
    def __init__(self, bus: EventBus, params: Optional[ProfileParams] = None):
        self.bus = bus
        self.p = params or ProfileParams()
        # Буферы: по ключу (symbol, tf) держим две очереди последних минут
        self.buf_daily: Dict[Tuple[str, str], Deque[dict]] = defaultdict(lambda: deque(maxlen=self.p.daily_minutes + 5))
        self.buf_sess:  Dict[Tuple[str, str], Deque[dict]] = defaultdict(lambda: deque(maxlen=self.p.session_minutes + 5))
        self._last_pub_ts: Dict[Tuple[str, str], float] = {}
        # delta-dedup: remember last published payload hash per (symbol, tf)
        self._last_payload_hash: Dict[Tuple[str, str], str] = {}
        # monotonically increasing sequence number per (symbol, tf)
        self._seq: Dict[Tuple[str, str], int] = defaultdict(int)

    # === публичный API ===
    def on_minute(self, candle: dict) -> None:
        """
        Ожидается словарь:
        {
          'symbol': 'BTCUSDT', 'tf': '1m',
          'open_time': int(ms), 'close_time': int(ms),
          'open': float, 'high': float, 'low': float, 'close': float,
          'volume': float, 'taker_buy_base': float (опц.)
        }
        """
        key = (candle["symbol"], candle["tf"])
        self.buf_daily[key].append(candle)
        self.buf_sess[key].append(candle)
        self._maybe_publish(key)

    # === внутренние ===
    def _format_and_dedupe(self, symbol: str, levels: List[dict]) -> List[dict]:
        """Normalize payload: keep one level per type (prefer higher heat), quantize price, stable sort by priority."""
        priority = [
            "VWAP_D", "VWAP_S", "POC_D", "POC_S",
            "VAH_D", "VAL_D", "VAH_S", "VAL_S",
            "HOD", "LOD", "SWING_H", "SWING_L", "ROUND"
        ]
        prio = {t: i for i, t in enumerate(priority)}
        best: Dict[str, dict] = {}
        for lv in levels:
            lt = str(lv.get("type", ""))
            if not lt:
                continue
            price = float(lv.get("price", 0.0))
            meta = lv.get("meta") or {}
            # Quantize price to reduce noisy updates; use per-symbol tick
            qprice = self._quantize_price(symbol, price)
            heat = float(meta.get("heat", 0.0) or 0.0)
            cand = {"type": lt, "price": qprice}
            if meta:
                cand["meta"] = meta
            prev = best.get(lt)
            if prev is None or float((prev.get("meta") or {}).get("heat", 0.0)) < heat:
                best[lt] = cand
        out = list(best.values())
        out.sort(key=lambda x: (prio.get(x.get("type", ""), 999), x.get("price", 0.0)))
        return out[:16]

    def _maybe_publish(self, key: Tuple[str, str], force: bool = False) -> None:
        now = time.time()
        last = self._last_pub_ts.get(key, 0.0)
        if not force and now - last < self.p.publish_throttle_s:
            return

        # Build raw levels from windows
        raw_levels: List[dict] = []
        for window_name, buf in (("D", self.buf_daily[key]), ("S", self.buf_sess[key])):
            if len(buf) < 10:
                continue
            raw_levels.extend(self._calc_window_levels(list(buf)))

        if not raw_levels:
            return

        # Normalize, dedupe, and sort
        symbol, tf = key
        norm_levels = self._format_and_dedupe(symbol, raw_levels)
        if not norm_levels:
            return

        payload_obj = {"version": 1, "symbol": symbol, "tf": tf, "levels": norm_levels}
        # Delta dedup via hash
        blob = json.dumps(payload_obj, sort_keys=True, separators=(",", ":"))
        h = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        if not force and self._last_payload_hash.get(key) == h:
            return
        self._last_payload_hash[key] = h
        self._last_pub_ts[key] = now
        self._seq[key] += 1
        payload_obj["seq"] = self._seq[key]

        # Publish
        self.bus.publish("levels.update", payload_obj)

    def flush(self, symbol: str, tf: str) -> None:
        """Force immediate publish of levels for (symbol, tf), ignoring throttle."""
        key = (symbol, tf)
        self._maybe_publish(key, force=True)

    def _calc_window_levels(self, rows: List[dict]) -> List[dict]:
        # VWAP
        tpv_sum = 0.0
        vol_sum = 0.0
        # соберём гистограмму объёма по цене
        hist: Dict[float, float] = defaultdict(float)

        for r in rows:
            h = float(r["high"]); l = float(r["low"]); c = float(r["close"]); v = float(r["volume"])
            typical = (h + l + c) / 3.0
            tpv_sum += typical * v
            vol_sum += v
            # объём распределяем по нескольким бинам: простая аппроксимация — весь объём в бине close
            bin_price = self._bin_price(c)
            hist[bin_price] += v

        # экстремумы окна (для HOD/LOD)
        try:
            hod = max(float(r["high"]) for r in rows)
            lod = min(float(r["low"])  for r in rows)
        except Exception:
            hod = None; lod = None

        vwap = tpv_sum / vol_sum if vol_sum > 0 else None
        if not vwap:
            return []

        # POC + Value Area
        if not hist:
            return []
        # отсортированный профиль
        bins = sorted(hist.items())  # [(price_bin, volume), ...]
        poc_price, poc_vol = max(bins, key=lambda kv: kv[1])

        # Value Area: минимум диапазона, покрывающий p.va_percent объёма
        total_vol = sum(v for _, v in bins)
        target = self.p.va_percent * total_vol
        # расширяемся от POC
        idx = [i for i, (bp, _) in enumerate(bins) if bp == poc_price]
        i0 = idx[0] if idx else bins.index((poc_price, poc_vol))
        va_low = va_high = poc_price
        acc = poc_vol
        left = i0 - 1; right = i0 + 1
        while acc < target and (left >= 0 or right < len(bins)):
            # на каждом шаге берём сторону с большим объёмом
            lv = bins[left][1] if left >= 0 else -1
            rv = bins[right][1] if right < len(bins) else -1
            if rv > lv:
                va_high = bins[right][0]; acc += max(rv, 0.0); right += 1
            else:
                va_low = bins[left][0];  acc += max(lv, 0.0); left -= 1

        # Небольшие метрики «теплоты» (heat) возле VWAP/POC как нормированная плотность
        max_vol = max(v for _, v in bins) or 1.0
        heat_at_vwap = hist.get(self._bin_price(vwap), 0.0) / max_vol
        heat_at_poc = hist.get(self._bin_price(poc_price), 0.0) / max_vol

        # Вернуть уровни с meta
        tag = "D" if len(rows) >= self.p.daily_minutes * 0.75 else "S"
        levels = [
            {"type": f"VWAP_{tag}", "price": float(vwap), "meta": {"heat": round(heat_at_vwap, 3)}},
            {"type": f"POC_{tag}",  "price": float(poc_price), "meta": {"heat": round(heat_at_poc, 3)}},
            {"type": f"VAH_{tag}",  "price": float(va_high)},
            {"type": f"VAL_{tag}",  "price": float(va_low)},
        ]
        # Добавим HOD/LOD для окна
        if hod is not None:
            levels.append({"type": "HOD", "price": float(hod)})
        if lod is not None:
            levels.append({"type": "LOD", "price": float(lod)})
        # Ближайший ROUND к VWAP по сетке round_steps
        if self.p.add_round and vwap is not None and self.p.round_steps:
            v = float(vwap)
            # выбираем шаг, который ближе всего к текущей цене (из списка шагов)
            step = min(self.p.round_steps, key=lambda s: abs((v % s)))
            # ближайшее округление к центру шага
            round_price = round(v / step) * step
            levels.append({"type": "ROUND", "price": float(round_price), "meta": {"basis": "VWAP", "step": float(step)}})
        return levels

    def _bin_price(self, price: float) -> float:
        if self.p.mode == "tick":
            step = max(self.p.binsize_tick, 1e-9)
            return round(price / step) * step
        # pct
        step = max(price * self.p.binsize_pct, 1e-9)
        # округление к ближайшему «центру» бина
        k = int(round(price / step))
        return k * step
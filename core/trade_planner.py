#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
import math
import time

try:
    # Фильтр новостей (опционально). Если модуля нет — просто игнорируем.
    from .news_guard import is_in_news_window, annotate_with_news
except Exception:
    def is_in_news_window(ts_ms: int) -> bool:
        return False
    def annotate_with_news(payload: dict) -> dict:
        return payload

from .event_bus import EventBus  # используется в проекте

# === Параметры риск-менеджмента/входа ===
RISK_PCT = 0.02                     # 2% от депо на СТОП
LADDER = [0.15, 0.35, 0.50]         # 15% / 35% / 50% входа в зоне
MIN_RR_HALF = 2.0                   # на 50% позиции минимум 2R
MIN_RR_FULL = 3.0                   # на 100% позиции минимум 3R
MARGIN_MODE = "isolated"            # торгуем только изолированную маржу

@dataclass
class AccountState:
    equity: float           # USDT
    max_leverage: float     # биржевой лимит по инструменту (например, 50х)

@dataclass
class PlannedOrder:
    side: str               # "buy" / "sell"
    price: float
    qty: float
    kind: str               # "limit" / "market"
    tag: str                # "L1/L2/L3" или "TP1/TP2/TP3" / "SL"

@dataclass
class Plan:
    symbol: str
    tf: str
    direction: str          # "long" / "short"
    entry_zone: Tuple[float, float]     # (low, high) зоны ФПФ
    ladder_orders: List[PlannedOrder]
    stop_price: float
    take_profits: List[PlannedOrder]    # TP1..TP3
    risk_notional: float
    est_position_notional: float
    est_leverage: float
    notes: Dict[str, str]

def _round_qty(symbol: str, qty: float) -> float:
    # упрощённо; при интеграции подставим шаг лота с биржи
    step = 1e-4
    return math.floor(qty / step) * step

def _pick_entry_points(direction: str, zone_low: float, zone_high: float, density_mid: Optional[float]) -> List[float]:
    """Три цены входа по «лесенке»: 15% ближняя граница, 35% середина/плотность, 50% дальняя граница."""
    if density_mid is None:
        mid = (zone_low + zone_high) / 2.0
    else:
        mid = float(density_mid)

    if direction == "long":
        return [zone_low, mid, zone_high]
    else:  # short
        return [zone_high, mid, zone_low]

def _ensure_rr(targets: List[float], entry_ref: float, stop: float, direction: str) -> List[float]:
    """Сдвигаем цели, чтобы RR соблюдался: 50% ≥ 2R, 100% ≥ 3R."""
    r = abs(entry_ref - stop)
    # индексы: 0 -> TP1 (20%), 1 -> TP2 (30%), 2 -> TP3 (50%)
    min2 = entry_ref + (2.0 * r if direction == "long" else -2.0 * r)
    min3 = entry_ref + (3.0 * r if direction == "long" else -3.0 * r)

    out = list(targets)
    # гарантируем, что последняя цель (сумма 100%) ≥ 3R
    if (direction == "long" and out[-1] < min3) or (direction == "short" and out[-1] > min3):
        out[-1] = min3
    # и что средняя цель ≥ 2R (для достижения ≥50% позиции к 2R)
    if (direction == "long" and out[1] < min2) or (direction == "short" and out[1] > min2):
        out[1] = min2
    # если TP1 «перевернулся» из‑за стопа — сдвигаем минимум на 1R
    min1 = entry_ref + (1.0 * r if direction == "long" else -1.0 * r)
    if (direction == "long" and out[0] < min1) or (direction == "short" and out[0] > min1):
        out[0] = min1
    return out

def _select_targets_from_levels(direction: str, entry_ref: float, levels: List[dict]) -> List[float]:
    """
    Выбор трёх целей по динамическим уровням/POC/VA.
    Сортируем по «силе» (POC > VWAP > VA > ROUND > SWING) и стороне движения, берём ближайшие 3.
    """
    if not levels:
        return []
    strength_order = {
        "POC_D": 5, "POC_S": 5,
        "VWAP_D": 4, "VWAP_S": 4,
        "VAH_D": 3, "VAL_D": 3, "VAH_S": 3, "VAL_S": 3,
        "ROUND": 2,
        "SWING_H": 1, "SWING_L": 1
    }
    cands = []
    for it in levels:
        try:
            lt = str(it.get("type"))
            px = float(it.get("price"))
            if direction == "long" and px <= entry_ref:
                continue
            if direction == "short" and px >= entry_ref:
                continue
            score = strength_order.get(lt, 0)
            cands.append((abs(px - entry_ref), -score, px))  # ближе и сильнее — лучше
        except Exception:
            continue
    if not cands:
        return []
    cands.sort()
    picked = [px for _,__,px in cands[:3]]
    # сортируем по стороне для читабельности
    return sorted(picked, reverse=(direction=="short"))

def plan_trade(bus: EventBus, account: AccountState, signal: dict) -> Optional[Plan]:
    """
    Принимает сигнал от детектора и строит план:
      - размер риска 2%,
      - расчёт количества и плеча от стопа,
      - лесенка 15/35/50 внутри зоны ФПФ,
      - 3 цели по уровням/POC/VA (с проверкой RR),
      - respect: окно новостей (запрет новых входов; пометка/перевод в б/у если открыто).
    """
    try:
        # базовые поля из сигнала (см. _emit_signal в детекторе)
        symbol = signal["symbol"]
        tf = signal["tf"]
        direction = signal["direction"]  # "long"/"short"
        break_price = float(signal["break_price"])
        # зона ФПФ: из сигнала — prefix_low/high (как минимум в нём есть экстремумы)
        zone_low = float(signal.get("prefix_low", break_price))
        zone_high = float(signal.get("prefix_high", break_price))
        level_meta = signal.get("level_meta") or {}
        # попытка достать «макс. плотность» для середины зоны (если есть)
        density_mid = level_meta.get("poc_price") or level_meta.get("density_peak")

        # стоп:
        # - на M5/M15 — за хай/лоу паттерна (детектор это уже использует);
        # - на H1/H4 — за ближайший сильный уровень (если доступен), иначе за экстремум.
        # В сигнале нет готового стопа -> оценим «предложенный» по простому правилу:
        ref_hi = float(signal.get("prefix_high", break_price))
        ref_lo = float(signal.get("prefix_low", break_price))
        tick = 1e-4
        if direction == "short":
            stop_price = ref_hi  # детально: можно добавить +N тиков
        else:
            stop_price = ref_lo

        # риск 2% от депозита
        risk_notional = account.equity * RISK_PCT
        stop_dist = abs(break_price - stop_price)
        if stop_dist <= 0:
            return None

        # требуемая позиция (но не превосходим максимально допустимое плечо по бирже)
        est_qty = risk_notional / stop_dist
        est_notional = est_qty * break_price
        est_leverage = min(account.max_leverage, max(1.0, est_notional / max(1e-9, account.equity)))

        # «лесенка» входа
        ladder_px = _pick_entry_points(direction, zone_low, zone_high, density_mid)
        ladder_qty = [est_qty * f for f in LADDER]
        ladder_orders = [
            PlannedOrder(
                side=("sell" if direction=="short" else "buy"),
                price=float(px),
                qty=_round_qty(symbol, q),
                kind="limit",
                tag=f"L{i+1}"
            )
            for i,(px,q) in enumerate(zip(ladder_px, ladder_qty))
        ]

        # выбор целей
        levels_payload = []  # сюда можно прокинуть актуальные уровни по символу/ТФ (если у тебя есть поток levels.update/snapshot)
        tps_from_lvls = _select_targets_from_levels(direction, break_price, levels_payload)
        # если уровней нет или мало — достроим RR-целями от входа
        if len(tps_from_lvls) < 3:
            # базовые R‑цели
            sign = 1.0 if direction == "long" else -1.0
            r = stop_dist
            rr_targets = [break_price + sign * r, break_price + sign * 2.0 * r, break_price + sign * 3.0 * r]
            # если каких-то целей хватает с уровней — объединяем, иначе берём RR
            tps = (tps_from_lvls + rr_targets)[:3]
        else:
            tps = tps_from_lvls[:3]

        # проверяем RR на 2R/3R и сдвигаем при необходимости
        tps_adj = _ensure_rr(tps, break_price, stop_price, direction)

        # распределяем 20% / 30% / 50%
        tp_fracs = [0.20, 0.30, 0.50]
        tp_orders = [
            PlannedOrder(
                side=("buy" if direction=="short" else "sell"),  # закрываем часть позиции
                price=float(px),
                qty=_round_qty(symbol, est_qty * f),
                kind="limit",
                tag=f"TP{i+1}"
            )
            for i,(px,f) in enumerate(zip(tps_adj, tp_fracs))
        ]

        # фильтр новостей: запрет входа и перевод в б/у
        ts_now_ms = int(time.time() * 1000)
        notes = {}
        if is_in_news_window(ts_now_ms):
            notes["news_window"] = "BLOCK_NEW_ORDERS_AND_SET_BREAKEVEN"
            # отметим план как «ограниченный новостями»
        plan = Plan(
            symbol=symbol,
            tf=tf,
            direction=direction,
            entry_zone=(zone_low, zone_high),
            ladder_orders=ladder_orders,
            stop_price=float(stop_price),
            take_profits=tp_orders,
            risk_notional=float(risk_notional),
            est_position_notional=float(est_notional),
            est_leverage=float(est_leverage),
            notes=notes
        )
        # опциональная аннотация новостями (для логов/отчётов)
        return annotate_with_news(plan.__dict__)
    except Exception:
        return None

# === Подписчик на сигналы ===

class TradePlanner:
    """Слушает шину сигналов и публикует торговый план в канал 'trade.plan'."""
    def __init__(self, bus: EventBus, account: AccountState):
        self.bus = bus
        self.account = account
        self.bus.subscribe("signal.detected", self._on_signal)

    def _on_signal(self, sig: dict):
        plan = plan_trade(self.bus, self.account, sig)
        if plan:
            # Отдаём в экзекьютор/логгер/GUI
            self.bus.publish("trade.plan", plan if isinstance(plan, Plan) else plan)


#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TradeExecutor — единый исполнитель торговых планов для демо и реала.

Идея:
- Получает планы из TradePlanner по шине событий (канал "trade.plan").
- НЕ размещает ордера сразу: ждёт подхода цены к зоне входа и только тогда ставит лесенку.
- Делает "поправку на ветер" — сдвигает лимитные цены на 5–15 тиков в сторону более вероятного исполнения.
- Работает через абстрактный интерфейс Broker (реальный/демо), чтобы не плодить отдельные файлы.
- Поддерживает изолированную маржу и установку плеча.
- На новостном окне (FOMC/NFP/CPI) блокирует новые входы и переводит позицию в безубыток.

Зависимости:
- core.event_bus.EventBus — простая шина publish/subscribe.
- core.news_guard — фильтр новостей (опционально, если модуля нет — логика новостей отключается).

Протокол сообщений:
- Вход:  bus.subscribe("trade.plan", on_plan) — план из TradePlanner (см. core/trade_planner.Plan/PlannedOrder)
- Тики:  bus.subscribe("market.tick", on_tick) — {symbol, price, ts_ms}
- Филлы: bus.subscribe("broker.fill", on_fill) — {symbol, side, price, qty, order_id, ts_ms}
- Позиции: bus.subscribe("position.update", on_pos) — {symbol, qty, avg_price, ts_ms}

Важно: Конкретные названия каналов можно адаптировать под ваш рантайм.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple, Protocol, Any
import time
import math

try:
    from .event_bus import EventBus
except Exception:  # простая заглушка, если EventBus не доступен
    class EventBus:
        def __init__(self):
            self._subs = {}
        def subscribe(self, topic: str, fn):
            self._subs.setdefault(topic, []).append(fn)
        def publish(self, topic: str, payload):
            for fn in self._subs.get(topic, []):
                try:
                    fn(payload)
                except Exception:
                    pass

try:
    from .news_guard import is_in_news_window
except Exception:
    def is_in_news_window(ts_ms: int, symbols: Optional[List[str]] = None, pre_s: int = 3600, post_s: int = 3600) -> bool:
        return False

# ==============================
# Абстрактный интерфейс брокера
# ==============================
class Broker(Protocol):
    """Мини-интерфейс брокера. Реализуется как демо (PaperBroker) или реальный адаптер.
    Все методы должны быть НЕ блокирующими и по возможности возвращать идентификаторы ордеров.
    """
    def set_margin_mode(self, symbol: str, mode: str) -> None: ...   # "isolated" или "cross"
    def set_leverage(self, symbol: str, leverage: float) -> None: ...
    def get_tick_size(self, symbol: str) -> float: ...               # шаг цены
    def get_lot_step(self, symbol: str) -> float: ...                # шаг количества
    def last_price(self, symbol: str) -> float: ...                  # последняя цена (если доступно)

    def place_limit(self, symbol: str, side: str, price: float, qty: float, tag: str) -> str: ...
    def place_market(self, symbol: str, side: str, qty: float, tag: str) -> str: ...
    def place_stop(self, symbol: str, side: str, stop_price: float, qty: float, tag: str) -> str: ...
    def place_take_profit(self, symbol: str, side: str, price: float, qty: float, tag: str) -> str: ...

    def cancel_order(self, symbol: str, order_id: str) -> None: ...

# ==============================
# Вспомогательные структуры
# ==============================
@dataclass
class LadderOrder:
    price: float
    qty: float
    tag: str
    order_id: Optional[str] = None
    placed: bool = False

@dataclass
class TPOrder:
    price: float
    qty: float
    tag: str
    order_id: Optional[str] = None
    placed: bool = False

@dataclass
class SLOrder:
    price: float
    qty: float
    tag: str = "SL"
    order_id: Optional[str] = None
    placed: bool = False

@dataclass
class PlanState:
    symbol: str
    tf: str
    direction: str              # long/short
    zone: Tuple[float, float]   # (low, high)
    stop_price: float
    ladder: List[LadderOrder]
    tps: List[TPOrder]
    risk_notional: float
    leverage: float
    # runtime
    activated: bool = False     # зона активирована (цена приблизилась) и ордера выставлены
    filled_qty: float = 0.0     # суммарно исполнено
    avg_entry: float = 0.0
    sl: Optional[SLOrder] = None
    put_on_breakeven: bool = True   # переводим в б/у после первого TP

# ==============================
# Вспомогательные функции
# ==============================

def _ceil_to_step(x: float, step: float) -> float:
    if step <= 0: return x
    return math.ceil(x / step) * step

def _floor_to_step(x: float, step: float) -> float:
    if step <= 0: return x
    return math.floor(x / step) * step

def _round_qty(step: float, qty: float) -> float:
    if step <= 0: return qty
    return math.floor(qty / step) * step

# смещение входных ордеров на 5–15 тиков в сторону более вероятного исполнения
def _wind_adjust(price: float, direction: str, tick: float, ticks_early: int) -> float:
    off = tick * max(1, int(ticks_early))
    if direction == "long":
        # хотим купить чуть раньше предполагаемой цены (чуть дороже)
        return price + off
    else:
        # хотим продать чуть раньше (чуть дешевле)
        return price - off

# ==============================
# Исполнитель
# ==============================
class TradeExecutor:
    def __init__(self,
                 bus: EventBus,
                 broker: Broker,
                 *,
                 margin_mode: str = "isolated",
                 activate_on_touch: bool = True,
                 activate_band_ticks: int = 50,   # сколько тиков вокруг зоны считаем «подходом»
                 wind_ticks_near: int = 5,
                 wind_ticks_far: int = 15,
                 breakeven_on_tp1: bool = True,
                 news_block_new: bool = True):
        self.bus = bus
        self.broker = broker
        self.margin_mode = margin_mode
        self.activate_on_touch = activate_on_touch
        self.activate_band_ticks = int(activate_band_ticks)
        self.wind_ticks_near = int(wind_ticks_near)
        self.wind_ticks_far = int(wind_ticks_far)
        self.breakeven_on_tp1 = breakeven_on_tp1
        self.news_block_new = news_block_new

        # состояние по символам
        self._plans: Dict[str, PlanState] = {}

        # подписки
        self.bus.subscribe("trade.plan", self._on_plan)
        self.bus.subscribe("market.tick", self._on_tick)
        self.bus.subscribe("broker.fill", self._on_fill)
        self.bus.subscribe("position.update", self._on_position_update)

    # -------- подписчики ---------
    def _on_plan(self, p: dict | Any):
        try:
            # допускаем словарь из TradePlanner или dataclass plan.__dict__
            plan = p if isinstance(p, dict) else getattr(p, "__dict__", {})
            symbol = plan.get("symbol"); tf = plan.get("tf"); direction = plan.get("direction")
            zone_low, zone_high = plan.get("entry_zone", (None, None))
            stop_price = float(plan.get("stop_price"))
            ladder_in = plan.get("ladder_orders") or []
            tps_in = plan.get("take_profits") or []
            lev = float(plan.get("est_leverage", 1.0))
            risk_notional = float(plan.get("risk_notional", 0.0))
            if not symbol or zone_low is None or zone_high is None:
                return
            tick = max(self.broker.get_tick_size(symbol), 1e-8)
            lot_step = max(self.broker.get_lot_step(symbol), 1e-8)

            # Готовим лесенку со сдвигом «на ветер» (ближайший шаг — меньше сдвиг)
            # L1 — ближняя граница, L3 — дальняя
            lorders: List[LadderOrder] = []
            for i, l in enumerate(ladder_in):
                px = float(getattr(l, "price", l.get("price")))
                qty = float(getattr(l, "qty", l.get("qty")))
                tag = str(getattr(l, "tag", l.get("tag", f"L{i+1}")))
                # чем дальше точка, тем больше сдвиг
                ticks_early = self.wind_ticks_near if i == 0 else (self.wind_ticks_far if i == 2 else (self.wind_ticks_near + self.wind_ticks_far)//2)
                adj = _wind_adjust(px, direction, tick, ticks_early)
                # привязываем к шагу цены
                adj_px = _floor_to_step(adj, tick) if direction == "long" else _ceil_to_step(adj, tick)
                lorders.append(LadderOrder(price=adj_px, qty=_round_qty(lot_step, qty), tag=tag))

            tporders: List[TPOrder] = []
            for i, t in enumerate(tps_in):
                px = float(getattr(t, "price", t.get("price")))
                qty = float(getattr(t, "qty", t.get("qty")))
                tag = str(getattr(t, "tag", t.get("tag", f"TP{i+1}")))
                adj_px = _ceil_to_step(px, tick) if direction == "long" else _floor_to_step(px, tick)
                tporders.append(TPOrder(price=adj_px, qty=_round_qty(lot_step, qty), tag=tag))

            sl = SLOrder(price=float(stop_price), qty=sum(lo.qty for lo in lorders))

            # установим режим изоляции и плечо
            try:
                self.broker.set_margin_mode(symbol, self.margin_mode)
                self.broker.set_leverage(symbol, max(1.0, lev))
            except Exception:
                pass

            self._plans[symbol] = PlanState(
                symbol=symbol, tf=tf, direction=direction,
                zone=(float(zone_low), float(zone_high)), stop_price=float(stop_price),
                ladder=lorders, tps=tporders, risk_notional=risk_notional,
                leverage=lev, sl=sl
            )
        except Exception:
            return

    def _on_tick(self, tick_msg: Dict[str, Any]):
        symbol = tick_msg.get("symbol"); price = tick_msg.get("price"); ts_ms = tick_msg.get("ts_ms")
        if symbol not in self._plans:
            return
        st = self._plans[symbol]
        # блокируем новые входы в окно новостей
        if self.news_block_new and is_in_news_window(int(ts_ms or time.time()*1000), symbols=[symbol]):
            return

        # если ещё не активировали — проверим приближение к зоне
        if not st.activated and self.activate_on_touch:
            if self._is_price_near_zone(symbol, price, st.zone, st.direction):
                self._activate(symbol)
        # если зона уже активирована — ничего не делаем; брокер выставил лимитки и ждём филлов

    def _on_fill(self, fill: Dict[str, Any]):
        symbol = fill.get("symbol"); side = fill.get("side"); price = float(fill.get("price", 0)); qty = float(fill.get("qty", 0))
        if symbol not in self._plans:
            return
        st = self._plans[symbol]
        # обновим среднюю цену и объём
        signed = qty if st.direction == "long" else -qty
        new_total = st.filled_qty + qty
        if new_total > 0:
            st.avg_entry = (st.avg_entry * st.filled_qty + price * qty) / new_total if st.filled_qty > 0 else price
        st.filled_qty = new_total
        # после первого филла — ставим SL/TP, если ещё не
        if st.sl and not st.sl.placed:
            try:
                # стоп всегда противоположной стороной от позиции
                sl_side = "sell" if st.direction == "long" else "buy"
                oid = self.broker.place_stop(symbol, sl_side, st.sl.price, st.sl.qty, st.sl.tag)
                st.sl.order_id = oid; st.sl.placed = True
            except Exception:
                pass
        for tp in st.tps:
            if not tp.placed:
                try:
                    tp_side = "sell" if st.direction == "long" else "buy"
                    oid = self.broker.place_take_profit(symbol, tp_side, tp.price, tp.qty, tp.tag)
                    tp.order_id = oid; tp.placed = True
                except Exception:
                    pass

    def _on_position_update(self, pos: Dict[str, Any]):
        # сюда можно повесить логику перевода в безубыток по достижении TP1 или при новостях
        symbol = pos.get("symbol"); qty = float(pos.get("qty", 0.0)); avg = float(pos.get("avg_price", 0.0))
        if symbol not in self._plans:
            return
        st = self._plans[symbol]
        ts_ms = int(pos.get("ts_ms", time.time()*1000))
        if qty == 0:
            return
        # перевод в безубыток при новостном окне
        if is_in_news_window(ts_ms, symbols=[symbol]):
            try:
                # переносим SL в б/у (чуть лучше, на 1–2 тика)
                tick = max(self.broker.get_tick_size(symbol), 1e-8)
                if st.direction == "long":
                    st.sl.price = avg + 2 * tick
                else:
                    st.sl.price = avg - 2 * tick
                if st.sl and st.sl.order_id:
                    # реализация обновления зависит от брокера; упростим: отмена+переустановка
                    self.broker.cancel_order(symbol, st.sl.order_id)
                    sl_side = "sell" if st.direction == "long" else "buy"
                    oid = self.broker.place_stop(symbol, sl_side, st.sl.price, st.sl.qty, st.sl.tag)
                    st.sl.order_id = oid
            except Exception:
                pass

    # -------- логика ---------
    def _is_price_near_zone(self, symbol: str, price: float, zone: Tuple[float, float], direction: str) -> bool:
        tick = max(self.broker.get_tick_size(symbol), 1e-8)
        low, high = zone
        band = self.activate_band_ticks * tick
        # считаем приближение как попадание цены в зону +/- band
        return (low - band) <= price <= (high + band)

    def _activate(self, symbol: str) -> None:
        st = self._plans.get(symbol)
        if not st or st.activated:
            return
        st.activated = True
        # разместим лесенку лимиток (уже с «поправкой на ветер»), SL и TP поставим после первого филла в _on_fill
        for lo in st.ladder:
            if lo.placed:
                continue
            try:
                side = "buy" if st.direction == "long" else "sell"
                oid = self.broker.place_limit(symbol, side, lo.price, lo.qty, lo.tag)
                lo.order_id = oid; lo.placed = True
                # публикуем лог-событие
                self.bus.publish("trade.order_submitted", {
                    "symbol": symbol, "tag": lo.tag, "price": lo.price, "qty": lo.qty,
                    "direction": st.direction, "ts_ms": int(time.time()*1000)
                })
            except Exception:
                continue

    # Утилита для внешнего сброса плана по символу
    def drop_plan(self, symbol: str) -> None:
        if symbol in self._plans:
            del self._plans[symbol]
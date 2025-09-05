from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Any

try:
    # local import, same style as in other core modules
    from .event_bus import EventBus
except Exception:  # pragma: no cover
    EventBus = object  # type: ignore


@dataclass
class ActiveSignal:
    # immutable basics
    signal_id: str
    symbol: str
    tf: str
    direction: str  # "long" | "short"
    entry: float
    sl: float
    tp1: float
    tp2: float
    ts_fix: int
    ts_detected: int
    ts_entry: int
    window_minutes: int

    # optional context to echo into outcome
    level_type: Optional[str] = None
    level_price: Optional[float] = None
    level_meta: Optional[dict] = None
    ai_score: Optional[int] = None

    # runtime tracking
    mfe_R: float = 0.0
    mae_R: float = 0.0
    t_hit_tp1: Optional[int] = None
    t_hit_tp2: Optional[int] = None
    t_hit_sl: Optional[int] = None

    def end_ts(self) -> int:
        return int(self.ts_entry + self.window_minutes * 60_000)

    @property
    def R(self) -> float:
        r = (self.entry - self.sl) if self.direction == "long" else (self.sl - self.entry)
        # guard against degenerate values
        return r if r > 0 else max(abs(self.entry) * 1e-4, 1e-6)


class OutcomeTracker:
    """
    Subscribes to `signal.detected` and `market.candle`, produces `signal.outcome`.
    Assumes detector emits at least: symbol, tf, direction, ts_fix, fix_close, prefix_low/high. SL placed beyond main prefix high/low with configurable tick offset.
    """

    def __init__(self, bus: Any, *, window_minutes: int = 360, stop_offset_ticks: int = 3):
        self.bus = bus
        self.window_minutes = int(window_minutes)
        self.stop_offset_ticks = max(1, int(stop_offset_ticks))
        self.active: Dict[str, ActiveSignal] = {}
        # subscriptions
        self.bus.subscribe("signal.detected", self._on_signal)
        self.bus.subscribe("market.candle", self._on_candle)

    # ---------------------- helpers ----------------------
    def _tick_for(self, symbol: str) -> float:
        # Basic per-symbol tick (can be moved to a symbol metadata service)
        return {
            "BTCUSDT": 0.5,
            "ETHUSDT": 0.05,
        }.get(symbol, 0.01)

    def _mk_id(self, msg: dict) -> str:
        # reasonably unique id for live tracking
        return f"{msg.get('symbol')}|{msg.get('tf')}|{msg.get('ts') or msg.get('ts_fix')}|{msg.get('direction')}"

    # ---------------------- event handlers ----------------------
    def _on_signal(self, msg: dict) -> None:
        try:
            if msg.get("direction") not in ("long", "short"):
                return
            symbol = str(msg.get("symbol") or msg.get("sym") or "")
            tf = str(msg.get("tf") or "1m")
            if not symbol:
                return

            # Prefer break (signal) timestamp & price; fallback to fix
            ts_break = msg.get("ts")
            ts_fix   = msg.get("ts_fix")
            ts_entry = int(ts_break if ts_break is not None else (ts_fix or 0))

            break_price = msg.get("break_price")
            fix_close   = msg.get("fix_close")
            entry = float(break_price if break_price is not None else (fix_close or 0.0))

            prefix_low  = msg.get("prefix_low")
            prefix_high = msg.get("prefix_high")
            if ts_entry <= 0 or entry == 0.0 or prefix_low is None or prefix_high is None:
                print(f"[OutcomeTracker] skip signal: missing fields entry={entry}, prefix_low={prefix_low}, prefix_high={prefix_high}, ts_entry={ts_entry}")
                return

            prefix_low = float(prefix_low); prefix_high = float(prefix_high)
            tick = self._tick_for(symbol)
            direction = str(msg.get("direction"))
            off = self.stop_offset_ticks * tick
            if direction == "long":
                # стоп под главным low префикса с запасом в off
                sl = prefix_low - off
                R = entry - sl
                tp1 = entry + R
                tp2 = entry + 2 * R
            else:
                # стоп над главным high префикса с запасом в off
                sl = prefix_high + off
                R = sl - entry
                tp1 = entry - R
                tp2 = entry - 2 * R

            sig_id = self._mk_id(msg)
            self.active[sig_id] = ActiveSignal(
                signal_id=sig_id,
                symbol=symbol,
                tf=tf,
                direction=direction,
                entry=float(entry),
                sl=float(sl),
                tp1=float(tp1),
                tp2=float(tp2),
                ts_fix=int(ts_fix or ts_entry),
                ts_detected=int(ts_break or ts_entry),
                ts_entry=int(ts_entry),
                window_minutes=self.window_minutes,
                level_type=msg.get("level_type"),
                level_price=float(msg.get("level_price")) if msg.get("level_price") is not None else None,
                level_meta=msg.get("level_meta") if isinstance(msg.get("level_meta"), dict) else None,
                ai_score=int(msg.get("ai_score")) if msg.get("ai_score") is not None else None,
            )
        except Exception:
            return

    def _on_candle(self, msg: dict) -> None:
        try:
            symbol = msg.get("symbol") or msg.get("sym")
            tf = msg.get("tf") or "1m"
            if not symbol:
                return
            # candle bounds
            high = float(msg.get("high"))
            low = float(msg.get("low"))
            ts = int(msg.get("close_time") or msg.get("ts") or msg.get("open_time") or 0)
            if ts <= 0:
                return

            to_remove = []
            for sig_id, st in list(self.active.items()):
                if st.symbol != symbol or st.tf != tf:
                    continue
                # update MFE/MAE in R
                if st.direction == "long":
                    st.mfe_R = max(st.mfe_R, (high - st.entry) / st.R)
                    st.mae_R = min(st.mae_R, (low - st.entry) / st.R)
                    # outcome checks
                    if low <= st.sl:
                        st.t_hit_sl = ts
                        self._publish_outcome(st, status="SL", now_ts=ts)
                        to_remove.append(sig_id); continue
                    if high >= st.tp2:
                        st.t_hit_tp2 = ts
                        if st.t_hit_tp1 is None:
                            st.t_hit_tp1 = ts
                        self._publish_outcome(st, status="TP2", now_ts=ts)
                        to_remove.append(sig_id); continue
                    if high >= st.tp1 and st.t_hit_tp1 is None:
                        st.t_hit_tp1 = ts
                else:  # short
                    st.mfe_R = max(st.mfe_R, (st.entry - low) / st.R)
                    st.mae_R = min(st.mae_R, (st.entry - high) / st.R)
                    if high >= st.sl:
                        st.t_hit_sl = ts
                        self._publish_outcome(st, status="SL", now_ts=ts)
                        to_remove.append(sig_id); continue
                    if low <= st.tp2:
                        st.t_hit_tp2 = ts
                        if st.t_hit_tp1 is None:
                            st.t_hit_tp1 = ts
                        self._publish_outcome(st, status="TP2", now_ts=ts)
                        to_remove.append(sig_id); continue
                    if low <= st.tp1 and st.t_hit_tp1 is None:
                        st.t_hit_tp1 = ts

                # timeout
                if ts >= st.end_ts():
                    self._publish_outcome(st, status="timeout", now_ts=ts)
                    to_remove.append(sig_id)

            for sid in to_remove:
                self.active.pop(sid, None)
        except Exception:
            return

    # ---------------------- publish ----------------------
    def _publish_outcome(self, st: ActiveSignal, *, status: str, now_ts: int) -> None:
        elapsed_min = int(max(0, (now_ts - st.ts_entry) // 60_000))
        payload = {
            "signal_id": st.signal_id,
            "symbol": st.symbol,
            "tf": st.tf,
            "direction": st.direction,
            "entry": st.entry,
            "sl": st.sl,
            "tp1": st.tp1,
            "tp2": st.tp2,
            "status": status,
            "t_hit_tp1": st.t_hit_tp1,
            "t_hit_tp2": st.t_hit_tp2,
            "t_hit_sl": st.t_hit_sl,
            "mfe_R": round(st.mfe_R, 4),
            "mae_R": round(st.mae_R, 4),
            "ts_entry": st.ts_entry,
            "entry_price": st.entry,
            "elapsed_min": elapsed_min,
            # echo level/score context for analytics
            "level_type": st.level_type,
            "level_price": st.level_price,
            "level_meta": st.level_meta,
            "ai_score": st.ai_score,
            "ts_fix": st.ts_fix,
        }
        try:
            self.bus.publish("signal.outcome", payload)
        except Exception:
            # best effort; in prod use logger
            pass
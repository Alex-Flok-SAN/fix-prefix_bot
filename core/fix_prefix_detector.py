from collections import deque
import collections
def get_fallback_levels(symbol, ts):
    # попытка взять уровни из кэша или построить на лету
    try:
        # level_cache must be available in the module scope or imported
        return level_cache.get(symbol, {}).get(ts, [])
    except Exception:
        return []

def refresh_volume_profile(symbol, tf):
    # принудительное обновление профиля
    try:
        # volume_profile_engine must be available in the module scope or imported
        volume_profile_engine.update(symbol, tf)
    except Exception:
        pass
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple
import statistics
import math
import hashlib
from .event_bus import EventBus
from datetime import datetime
from urllib.parse import quote

@dataclass
class Candle:
    ts_open: int
    ts_close: int
    o: float; h: float; l: float; c: float; v: float
    # optional list of level dicts present on this bar: [{"type": str, "price": float, "meta": {...}}]
    levels: Optional[List[dict]] = None

@dataclass
class FixState:
    fix_high: Optional[float] = None
    fix_low: Optional[float] = None
    fix_high_ts: Optional[int] = None
    fix_low_ts: Optional[int] = None
    fix_high_close: Optional[float] = None
    fix_low_close: Optional[float] = None
    return_ts: Optional[int] = None
    vol_fix: Optional[float] = None
    level_type: Optional[str] = None
    level_price: Optional[float] = None
    level_meta: Optional[dict] = None
    # idle -> got_fix_high -> got_fix_low -> both_high_low -> both_low_high -> returned_short -> returned_long
    # -> await_retest_short -> await_retest_long (for entry_mode "retest1")
    stage: str = "idle"
    last_signal_fix_ts: Optional[int] = None
    matched_levels: Optional[List[str]] = None
    matched_count: int = 0
    # For retest1 entry mode: store break info to use on retest candle
    pending_break_ts: Optional[int] = None
    pending_break_price: Optional[float] = None

class FixPrefixDetector:
    """Детектор паттерна Фикс‑Префикс (v1, по закрытым свечам).
    Логика (шорт):
      1) pivot HIGH с объёмом выше X * SMA(vol, N) -> фикс-вершина
      2) затем pivot LOW -> фикс-лоу
      3) цена возвращается выше фикс-вершины (close > fix_high) -> returned
      4) свеча закрывается ниже фикс-лоу -> сигнал SHORT
    Лонг — зеркально.
    Пивоты определяются по центру окна (L слева, R справа).
    entry_mode: "break" (default) — сигнал сразу на пробой;
                "retest1" — ждём одну свечу ретеста после пробоя, сигнал только если подтверждается ретестом.
    """
    def __init__(self, bus: EventBus, L: int = 2, R: int = 2, vol_mult: float = 1.2, vol_sma_n: int = 20, min_bars_between: int = 1, zone_eps: float = 0.00025,
                 eps_touch_pct: float = 0.0020,  # 0.20%
                 level_priority: Optional[List[str]] = None,
                 eps_mult_by_level: Optional[Dict[str, float]] = None,
                 range_k_base: float = 1.02,
                 vol_round_mult: float = 1.00,
                 require_conf_for_round: bool = False,
                 range_k_round_bonus: float = 0.15,
                 disable_swing_without_conf: bool = False,
                 min_stop_ticks: int = 1,
                 active_hours: Optional[Tuple[int,int]] = None,
                 stop_offset_ticks: int = 4,
                 entry_mode: str = "break",
                 # --- new universalization knobs ---
                 tick_size_map: Optional[Dict[str, float]] = None,
                 bar_ms_by_tf: Optional[Dict[str, int]] = None,
                 lock_level_on_fix: bool = False,
                 allow_level_upgrade: bool = True,
                 min_stop_alpha: float = 0.0,
                 # --- retest entry mode knobs ---
                 retest_only_for_levels: Optional[List[str]] = None,
                 retest_min_conf: int = 2,
                 retest_for_long: bool = False,
                 retest_for_short: bool = False
                 ,
                 # --- per-symbol profiles & alt-impulse knobs ---
                 symbol_profiles: Optional[Dict[str, dict]] = None,
                 alt_imp_near: float = 0.90,
                 alt_vol_boost: float = 1.10
                 ):
        self.bus = bus
        self.L = L; self.R = R
        self.vol_mult = vol_mult
        self.vol_sma_n = vol_sma_n
        self.min_bars_between = min_bars_between
        self.zone_eps = zone_eps
        self.buffers: Dict[Tuple[str,str], Deque[Candle]] = {}
        self.states: Dict[Tuple[str,str], FixState] = {}
        self.eps_touch_pct = eps_touch_pct
        self.level_priority = level_priority or [
            "DYN_M", "DYN_W",  # monthly/weekly dynamic levels (new, highest priority)
            "VWAP_D","VWAP_S","POC_D","POC_S","VAH_D","VAL_D","VAH_S","VAL_S",
            "HOD","LOD","SWING_H","SWING_L","ROUND"
        ]
        # eps by base type; VA* treated as VA
        self.eps_mult_by_level = eps_mult_by_level or {
            "SWING_H": 0.5, "SWING_L": 0.5, "ROUND": 1.0,
            "VWAP": 1.0, "POC": 1.0, "VA": 1.0, "HOD": 1.0, "LOD": 1.0,
            "DYN": 1.0  # new: dynamic monthly/weekly
        }
        self.range_k_base = range_k_base
        self.vol_round_mult = vol_round_mult
        self.require_conf_for_round = require_conf_for_round
        self.range_k_round_bonus = range_k_round_bonus
        self.disable_swing_without_conf = disable_swing_without_conf
        self.min_stop_ticks = int(min_stop_ticks)
        self.active_hours = active_hours
        self.stop_offset_ticks = int(stop_offset_ticks)
        self.entry_mode = entry_mode if entry_mode in ("break", "retest1") else "break"
        self.retest_only_for_levels = retest_only_for_levels
        self.retest_min_conf = int(retest_min_conf)
        self.retest_for_long = bool(retest_for_long)
        self.retest_for_short = bool(retest_for_short)
        # symbol profiles
        self.symbol_profiles: Dict[str, dict] = symbol_profiles or {
            # ETHUSDT left by defaults
            "SOLUSDT": {"vol_mult": 1.15, "eps_touch_pct": 0.0022, "range_k_base": 1.00, "vol_round_mult": 1.00, "stop_offset_ticks": 4, "alt_imp_near": 0.90, "alt_vol_boost": 1.08},
            # BNB: обновлённый профиль
            "BNBUSDT": {"vol_mult": 1.00, "eps_touch_pct": 0.0027, "range_k_base": 0.98, "vol_round_mult": 0.92, "stop_offset_ticks": 5, "alt_imp_near": 0.85, "alt_vol_boost": 1.04},
            # DOGE: слабее импульс, мягкий объём и ROUND
            "DOGEUSDT": {"vol_mult": 1.05, "eps_touch_pct": 0.0028, "range_k_base": 1.00, "vol_round_mult": 0.92, "stop_offset_ticks": 5, "alt_imp_near": 0.80, "alt_vol_boost": 1.00},
            # Новые пары — стандартный мягкий профиль как у SOL
            "ADAUSDT": {"vol_mult": 1.12, "eps_touch_pct": 0.0025, "range_k_base": 0.98, "vol_round_mult": 0.98, "stop_offset_ticks": 4, "alt_imp_near": 0.88, "alt_vol_boost": 1.08},
            "LTCUSDT": {"vol_mult": 1.15, "eps_touch_pct": 0.0022, "range_k_base": 1.00, "vol_round_mult": 1.00, "stop_offset_ticks": 4, "alt_imp_near": 0.90, "alt_vol_boost": 1.08},
            "AVAXUSDT": {"vol_mult": 1.10, "eps_touch_pct": 0.0025, "range_k_base": 0.99, "vol_round_mult": 0.98, "stop_offset_ticks": 4, "alt_imp_near": 0.88, "alt_vol_boost": 1.08},
            "XRPUSDT": {"vol_mult": 1.15, "eps_touch_pct": 0.0025, "range_k_base": 1.00, "vol_round_mult": 0.98, "stop_offset_ticks": 4, "alt_imp_near": 0.90, "alt_vol_boost": 1.08},
            # "ENAUSDT": {"vol_mult": 1.15, "eps_touch_pct": 0.0022, "range_k_base": 1.00, "vol_round_mult": 1.00, "stop_offset_ticks": 4, "alt_imp_near": 0.90, "alt_vol_boost": 1.08},
        }
        self.alt_imp_near = float(alt_imp_near)
        self.alt_vol_boost = float(alt_vol_boost)
        # market specifics / timeframe resolution
        self.tick_size_map: Dict[str, float] = tick_size_map or {}
        self.bar_ms_by_tf: Dict[str, int] = bar_ms_by_tf or {
            "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
            "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000
        }
        # level handling policy
        self.lock_level_on_fix = bool(lock_level_on_fix)
        self.allow_level_upgrade = bool(allow_level_upgrade)
        # dynamic min stop: additional share of short-range (in ticks)
        self.min_stop_alpha = float(min_stop_alpha)
        # cache: last known levels per (symbol, tf)
        self._levels_cache: Dict[Tuple[str, str], List[dict]] = {}
        # diagnostics counters
        self.stats = collections.Counter()
        # subscribe to external level updates
        try:
            self.bus.subscribe("levels.update", self._on_levels_update)
        except Exception:
            pass
    def _tv_interval(self, tf: str) -> str:
        """Map timeframe key to TradingView interval string."""
        interval_map = {
            "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
            "1h": "60", "4h": "240", "1d": "D"
        }
        return interval_map.get(tf, "60")

    def _build_tv_url(self, symbol: str, tf: str, ts: int) -> str:
        """Robust TradingView URL anchored at `ts`.
        We pass both query `time=` and hash `#time=` to avoid fallbacks to 'now' in some builds.
        Accepts ms or seconds; converts to seconds.
        """
        tv_symbol = f"BINANCE:{symbol}.P"
        interval = self._tv_interval(tf)
        if ts is None:
            return f"https://www.tradingview.com/chart/?symbol={quote(tv_symbol)}&interval={interval}"
        ts_sec = int(ts // 1000) if int(ts) > 10_000_000_000 else int(ts)
        base = f"https://www.tradingview.com/chart/?symbol={quote(tv_symbol)}&interval={interval}&time={ts_sec}&range=300"
        return base + f"#time={ts_sec}"

    def _group_id(self, symbol: str, tf: str, direction: str, level_price: Optional[float], ts_fix: Optional[int]) -> str:
        """Stable group id for multi‑TF merge and dedup: symbol, dir, level bucket, time bucket."""
        try:
            tick = self._tick_for_symbol(symbol)
            lvl_bucket = 0 if level_price is None else int(round(float(level_price) / max(tick, 1e-9)))
            bar_ms = self._bar_ms_for_tf(tf)
            t_bucket = 0 if not ts_fix else int(int(ts_fix) // max(1, 3 * bar_ms))
            raw = f"{symbol}|{tf}|{direction}|{lvl_bucket}|{t_bucket}"
            return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]
        except Exception:
            return ""

    def _stat(self, reason: str) -> None:
        try:
            self.stats[reason] += 1
        except Exception:
            pass

    def _debug_reject(self, key: Tuple[str,str], st: FixState, candle: Optional[Candle], reason: str, **kwargs) -> None:
        """Verbose one-line diagnostics for rejected candidates."""
        try:
            symbol, tf = key
            stage = getattr(st, 'stage', None)
            lvl = f"{st.level_type}@{st.level_price}" if getattr(st, 'level_type', None) else "None"
            base = [
                f"[why] {key} {reason} stage={stage}",
                f"level={lvl} conf={getattr(st, 'matched_count', 0)}",
            ]
            if candle is not None:
                base.append(
                    f"ts={candle.ts_close} ohlc=({candle.o},{candle.h},{candle.l},{candle.c}) v={candle.v}"
                )
            for k, v in kwargs.items():
                base.append(f"{k}={v}")
            print("  " + " | ".join(base))
        except Exception:
            pass

    def dump_stats(self) -> None:
        try:
            print("\n[detector.stats]")
            total_candidates = self.stats.get('candidate', 0)
            ok = self.stats.get('ok_long', 0) + self.stats.get('ok_short', 0)
            for k, v in sorted(self.stats.items(), key=lambda kv: (-kv[1], kv[0])):
                print(f"  {k:18s}: {v}")
            if total_candidates:
                conv = ok / total_candidates
                print(f"  conversion_ok     : {ok}/{total_candidates} = {conv:.2%}")
            print()
        except Exception:
            pass

    def on_candle(self, candle: dict):
        key = (candle['symbol'], candle['tf'])
        buf = self.buffers.setdefault(
            key,
            deque(maxlen=max(200, 5 * (self.L + self.R) + self.vol_sma_n + 100))
        )
        st = self.states.setdefault(key, FixState())

        # optional per-bar levels: expect list of dicts {"type": str, "price": float, "meta": {...}}
        levels_payload = candle.get('levels')
        levels_list: Optional[List[dict]] = None
        if isinstance(levels_payload, list):
            tmp = []
            for it in levels_payload:
                if not isinstance(it, dict):
                    continue
                try:
                    lt = str(it.get('type'))
                    lp = float(it.get('price'))
                    meta = it.get('meta') if isinstance(it.get('meta'), dict) else None
                    tmp.append({"type": lt, "price": lp, "meta": meta})
                except Exception:
                    continue
            levels_list = tmp or None
        # если уровни не переданы в свече, берём последние из кэша
        if not levels_list:
            cached = self._levels_cache.get(key)
            if cached:
                levels_list = cached

        buf.append(Candle(
            ts_open=candle['open_time'], ts_close=candle['close_time'],
            o=candle['open'], h=candle['high'], l=candle['low'],
            c=candle['close'], v=candle['volume'],
            levels=levels_list
        ))
        # Когда накопили окно для пивота — проверяем центральную свечу
        self._check_pivot_and_state(key)

    def _on_levels_update(self, msg: dict):
        """Handle external level updates.
        Expected payload:
          {
            "symbol": "BTCUSDT",
            "tf": "1m",  # timeframe key to match detector buffers
            "levels": [
               {"type": "VWAP", "price": 67890.0, "meta": {...}},
               {"type": "ROUND", "price": 68000.0, "meta": {...}},
               ...
            ]
          }
        """
        try:
            symbol = str(msg.get("symbol"))
            tf = str(msg.get("tf"))
            if not symbol or not tf:
                return
            # Ensure profile is refreshed for BNBUSDT or DOGEUSDT
            if symbol in ("BNBUSDT", "DOGEUSDT"):
                refresh_volume_profile(symbol, tf)
            payload = msg.get("levels")
            if not isinstance(payload, list):
                return
            out: List[dict] = []
            for it in payload:
                if not isinstance(it, dict):
                    continue
                try:
                    lt = str(it.get("type"))
                    lp = float(it.get("price"))
                    meta = it.get("meta") if isinstance(it.get("meta"), dict) else None
                    if lt and lp == lp:
                        out.append({"type": lt, "price": lp, "meta": meta})
                except Exception:
                    continue
            if out:
                self._levels_cache[(symbol, tf)] = out
        except Exception:
            pass
    def _base_type(self, lt: str) -> str:
        if lt.startswith("VWAP"): return "VWAP"
        if lt.startswith("POC"):  return "POC"
        if lt.startswith("VAH") or lt.startswith("VAL"): return "VA"
        if lt.startswith("DYN_"): return "DYN"
        return lt

    def _eps_mult_for(self, lt: str) -> float:
        return self.eps_mult_by_level.get(self._base_type(lt), 1.0)

    def _bar_ms_for_tf(self, tf: str) -> int:
        try:
            return int(self.bar_ms_by_tf.get(tf, 60_000))
        except Exception:
            return 60_000

    def _entry_mode_for(self, st: FixState, direction: str) -> str:
        """Decide entry mode (break or retest1) conditionally per direction/level/conf.
        Rules:
          - If `self.entry_mode` is explicitly set to "retest1", always use retest.
          - Otherwise start with "break" and switch to "retest1" only if:
              * direction matches retest_for_long/short flag, and
              * (retest_only_for_levels is None or level_type is in it), and
              * matched confluence >= retest_min_conf.
        """
        # If user forced global retest, honor it
        if self.entry_mode == "retest1":
            return "retest1"
        # Default
        mode = "break"
        try:
            lt = (st.level_type or "")
            conf_n = int(getattr(st, "matched_count", 0) or 0)
            dir_ok = (direction == "long" and self.retest_for_long) or (direction == "short" and self.retest_for_short)
            lvl_ok = (self.retest_only_for_levels is None) or (lt in self.retest_only_for_levels)
            conf_ok = conf_n >= int(self.retest_min_conf)
            if dir_ok and lvl_ok and conf_ok:
                mode = "retest1"
        except Exception:
            pass
        return mode

    # ---- helpers ----

    def _tick_for_symbol(self, symbol: str) -> float:
        # Prefer user-provided map; fall back to common defaults; then a safe tiny default
        if symbol in self.tick_size_map:
            return float(self.tick_size_map[symbol])
        return {
            "BTCUSDT": 0.5,
            "ETHUSDT": 0.05,
        }.get(symbol, 0.01)
    def _calc_ai_score(self, level_type: Optional[str], level_meta: Optional[dict], direction: Optional[str]) -> int:
        # Base
        score = 50
        lt = (level_type or "").upper()
        heat = float(level_meta.get("heat", 0.0)) if isinstance(level_meta, dict) else 0.0
        # Bonuses by type
        if lt.startswith("POC"): score += 15
        if lt.startswith("VWAP"): score += 10
        if lt.startswith("VAH") or lt.startswith("VAL"): score += 8
        if lt.startswith("DYN_M"): score += 18
        if lt.startswith("DYN_W"): score += 12
        # Heat contribution (0..1) -> up to +20
        score += int(round(min(max(heat, 0.0), 1.0) * 20))
        # Synergy: dynamic + POC/VA in meta
        try:
            if lt.startswith("DYN_") and isinstance(level_meta, dict):
                has_poc = bool(level_meta.get("poc") or level_meta.get("poc_price"))
                has_va = bool(level_meta.get("val") or level_meta.get("vah"))
                if has_poc: score += 8
                if has_va: score += 5
        except Exception:
            pass
        # ROUND penalty if cold
        if lt == "ROUND" and heat < 0.2:
            score -= 10
        # Clamp
        return int(max(1, min(100, score)))

    def _check_pivot_and_state(self, key: Tuple[str,str]):
        buf = self.buffers[key]
        st = self.states[key]
        # Per-symbol effective parameters (fallback to detector defaults)
        _prof = getattr(self, "symbol_profiles", {}).get(key[0], {})
        range_k_base_eff = float(_prof.get("range_k_base", self.range_k_base))
        vol_mult_eff = float(_prof.get("vol_mult", self.vol_mult))
        vol_round_mult_eff = float(_prof.get("vol_round_mult", self.vol_round_mult))
        eps_touch_pct_eff = float(_prof.get("eps_touch_pct", self.eps_touch_pct))
        stop_offset_ticks_eff = int(_prof.get("stop_offset_ticks", self.stop_offset_ticks))
        alt_imp_near_eff = float(_prof.get("alt_imp_near", getattr(self, "alt_imp_near", 0.90)))
        alt_vol_boost_eff = float(_prof.get("alt_vol_boost", getattr(self, "alt_vol_boost", 1.10)))
        if len(buf) < (self.L + self.R + 1):
            return

        # Центр окна — свеча на позиции -R-1
        center_idx = len(buf) - self.R - 1
        if center_idx <= self.L - 1:
            return
        seq = list(buf)
        center = seq[center_idx]
        last = buf[-1]  # последняя закрытая свеча (она и является кандидатом на возврат/пробой)

        left = seq[center_idx - self.L:center_idx]
        right = seq[center_idx + 1:center_idx + 1 + self.R]
        if len(left) < self.L or len(right) < self.R:
            return

        is_pivot_high = all(center.h > x.h for x in left) and all(center.h > x.h for x in right)
        is_pivot_low  = all(center.l < x.l for x in left) and all(center.l < x.l for x in right)

        # volume SMA по последним vol_sma_n баров ДО центра
        vols = [x.v for x in seq[:center_idx]]
        vol_ok = True
        if len(vols) >= self.vol_sma_n:
            sma = statistics.fmean(vols[-self.vol_sma_n:])
            vol_ok = center.v >= vol_mult_eff * sma if sma else True

        # Allow pivots without heavy volume if strong level/confluence near the pivot price
        strong_high = False
        strong_low = False
        try:
            ltH, LH, LMH, MTH = self._pick_level(center.h, center.levels)
            confH = len(MTH)
            strong_types = {"DYN_M","DYN_W","POC_D","POC_S","VWAP_D","VWAP_S","VAH_D","VAL_D","VAH_S","VAL_S"}
            strong_high = bool((ltH in strong_types) or (confH >= 2) or ((LMH or {}).get("heat", 0.0) >= 0.4))
        except Exception:
            pass
        try:
            ltL, LL, LML, MTL = self._pick_level(center.l, center.levels)
            confL = len(MTL)
            strong_types = {"DYN_M","DYN_W","POC_D","POC_S","VWAP_D","VWAP_S","VAH_D","VAL_D","VAH_S","VAL_S"}
            strong_low = bool((ltL in strong_types) or (confL >= 2) or ((LML or {}).get("heat", 0.0) >= 0.4))
        except Exception:
            pass

        # === 1) Стартовые пивоты ===
        if st.stage == "idle":
            if is_pivot_high and (vol_ok or strong_high):
                st.fix_high = center.h
                st.fix_high_ts = center.ts_close
                st.fix_high_close = center.c
                st.fix_low = None
                st.fix_low_ts = None
                st.fix_low_close = None
                st.return_ts = None
                st.vol_fix = center.v
                lt, L, LM, MT = self._pick_level(center.h, center.levels)
                if not lt:
                    # fallback logic for no_levels
                    levels_found = []
                    ts_prefix = center.ts_close
                    levels_found = get_fallback_levels(key[0], ts_prefix)
                    if levels_found:
                        # try to pick level from fallback
                        lt, L, LM, MT = self._pick_level(center.h, levels_found)
                    if not lt:
                        self._stat('no_levels')
                        self._debug_reject(key, st, center, 'no_levels', price=center.h, eps_pct=eps_touch_pct_eff)
                st.level_type = lt
                st.level_price = L
                st.level_meta = LM
                st.matched_levels = MT or None
                st.matched_count = len(MT)
                st.stage = "got_fix_high"
                print(f"[FPF] {key} FIX_HIGH at {center.h} vol={center.v} ts_close={center.ts_close}")
                self._emit_setup(key, "FIX_HIGH", center.h, center.ts_close)
            elif is_pivot_low and (vol_ok or strong_low):
                st.fix_low = center.l
                st.fix_low_ts = center.ts_close
                st.fix_low_close = center.c
                st.fix_high = None
                st.fix_high_ts = None
                st.fix_high_close = None
                st.return_ts = None
                st.vol_fix = center.v
                lt, L, LM, MT = self._pick_level(center.l, center.levels)
                if not lt:
                    # fallback logic for no_levels
                    levels_found = []
                    ts_prefix = center.ts_close
                    levels_found = get_fallback_levels(key[0], ts_prefix)
                    if levels_found:
                        lt, L, LM, MT = self._pick_level(center.l, levels_found)
                    if not lt:
                        self._stat('no_levels')
                        self._debug_reject(key, st, center, 'no_levels', price=center.l, eps_pct=self.eps_touch_pct)
                st.level_type = lt
                st.level_price = L
                st.level_meta = LM
                st.matched_levels = MT or None
                st.matched_count = len(MT)
                st.stage = "got_fix_low"
                print(f"[FPF] {key} FIX_LOW at {center.l} vol={center.v} ts_close={center.ts_close}")
                self._emit_setup(key, "FIX_LOW", center.l, center.ts_close)
            return

        # === 2) Добираем вторую точку ===
        if st.stage == "got_fix_high":
            # ждём pivot low после фикса
            if is_pivot_low and center.ts_close > (st.fix_high_ts or 0) and (center.ts_close - (st.fix_high_ts or 0)) >= self.min_bars_between * self._bar_ms_for_tf(key[1]):
                st.fix_low = center.l
                st.fix_low_ts = center.ts_close
                st.fix_low_close = center.c
                st.stage = "both_high_low"
                print(f"[FPF] {key} got FIX_LOW after FIX_HIGH: {st.fix_low}")
                self._emit_setup(key, "FIX_LOW", st.fix_low, st.fix_low_ts)
        elif st.stage == "got_fix_low":
            # ждём pivot high после фикса
            if is_pivot_high and center.ts_close > (st.fix_low_ts or 0) and (center.ts_close - (st.fix_low_ts or 0)) >= self.min_bars_between * self._bar_ms_for_tf(key[1]):
                st.fix_high = center.h
                st.fix_high_ts = center.ts_close
                st.fix_high_close = center.c
                st.stage = "both_low_high"
                print(f"[FPF] {key} got FIX_HIGH after FIX_LOW: {st.fix_high}")
                self._emit_setup(key, "FIX_HIGH", st.fix_high, st.fix_high_ts)

        # === 3) Возврат к зоне ===
        if st.stage == "both_high_low":
            # refresh level based on last bar (prefer more relevant level) unless locked
            if not self.lock_level_on_fix:
                lt2, L2, LM2, MT2 = self._pick_level(last.h, last.levels)
                if not lt2:
                    # fallback logic for no_levels
                    levels_found = []
                    ts_prefix = last.ts_close
                    levels_found = get_fallback_levels(key[0], ts_prefix)
                    if levels_found:
                        lt2, L2, LM2, MT2 = self._pick_level(last.h, levels_found)
                    if not lt2:
                        self._debug_reject(key, st, last, 'no_levels', price=last.h, eps_pct=eps_touch_pct_eff)
                if lt2 and L2:
                    # upgrade only to a higher-priority level if requested
                    if (st.level_type is None) or (self.allow_level_upgrade and self.level_priority.index(lt2) < self.level_priority.index(st.level_type)):
                        st.level_type, st.level_price, st.level_meta = lt2, L2, LM2
                    st.matched_levels = MT2 or None
                    st.matched_count = len(MT2)
            eps_abs = abs((st.level_price or st.fix_high or last.h)) * eps_touch_pct_eff * self._eps_mult_for(st.level_type or "ROUND")
            # сценарий шорта: возврат к зоне фикс-хая считаем по High свечи
            if st.fix_high is not None and last.h >= (st.fix_high - eps_abs) and self._near_level(last.h, st.level_type, st.level_price):
                st.return_ts = last.ts_close
                st.stage = "returned_short"
                self._stat('candidate')
                print(f"[FPF] {key} returned above FIX_HIGH={st.fix_high} at ts={st.return_ts}; waiting for break below FIX_LOW={st.fix_low}")
                self._emit_setup(key, "RETURN", last.c, st.return_ts)
        elif st.stage == "both_low_high":
            # refresh level based on last bar (prefer more relevant level) unless locked
            if not self.lock_level_on_fix:
                lt2, L2, LM2, MT2 = self._pick_level(last.l, last.levels)
                if not lt2:
                    # fallback logic for no_levels
                    levels_found = []
                    ts_prefix = last.ts_close
                    levels_found = get_fallback_levels(key[0], ts_prefix)
                    if levels_found:
                        lt2, L2, LM2, MT2 = self._pick_level(last.l, levels_found)
                    if not lt2:
                        self._debug_reject(key, st, last, 'no_levels', price=last.l, eps_pct=eps_touch_pct_eff)
                if lt2 and L2:
                    if (st.level_type is None) or (self.allow_level_upgrade and self.level_priority.index(lt2) < self.level_priority.index(st.level_type)):
                        st.level_type, st.level_price, st.level_meta = lt2, L2, LM2
                    st.matched_levels = MT2 or None
                    st.matched_count = len(MT2)
            eps_abs = abs((st.level_price or st.fix_low or last.l)) * eps_touch_pct_eff * self._eps_mult_for(st.level_type or "ROUND")
            # сценарий лонга: возврат к зоне фикс-лоу считаем по Low свечи
            if st.fix_low is not None and last.l <= (st.fix_low + eps_abs) and self._near_level(last.l, st.level_type, st.level_price):
                st.return_ts = last.ts_close
                st.stage = "returned_long"
                self._stat('candidate')
                print(f"[FPF] {key} returned below FIX_LOW={st.fix_low} at ts={st.return_ts}; waiting for break above FIX_HIGH={st.fix_high}")
                self._emit_setup(key, "RETURN", last.c, st.return_ts)

        # === 4) Пробой и сигнал ===
        if st.stage == "returned_short":
            seq = list(buf)
            ranges = [x.h - x.l for x in seq]
            # stronger impulse if ROUND without confluence
            k_adj = 0.0
            if st.level_type == "ROUND" and self.require_conf_for_round and (st.matched_count or 0) < 2:
                k_adj += self.range_k_round_bonus
            k_base = range_k_base_eff + k_adj
            if (st.matched_count or 0) >= 2:
                k_base = max(1.0, k_base - 0.25)
            # If dynamic monthly/weekly is part of confluence, allow a bit softer k
            try:
                if any(t in (st.matched_levels or []) for t in ("DYN_M","DYN_W")):
                    k_base = max(1.0, k_base - 0.08)
            except Exception:
                pass
            _imp = self._impulse_metrics(ranges[:-1], (last.h - last.l), k_base=k_base)
            rng_ok = (last.h - last.l) >= _imp["threshold"]
            # Alternative impulse pass: near-threshold + (volume boost or confluence)
            rng_alt_ok = False
            if len(seq) > self.vol_sma_n:
                vol_sma_last = statistics.fmean([x.v for x in seq[-self.vol_sma_n-1:-1]])
                vol_boost = (last.v >= alt_vol_boost_eff * vol_sma_last) if vol_sma_last else True
            else:
                vol_boost = True
            conf_boost = (st.matched_count or 0) >= 2
            near_threshold = (last.h - last.l) >= alt_imp_near_eff * _imp["threshold"]
            rng_alt_ok = bool(near_threshold and (vol_boost or conf_boost))
            # volume gate for ROUND, skip if DYN_M or DYN_W in confluence
            vol_ok_round = True
            if st.level_type == "ROUND" and len(seq) > self.vol_sma_n and ("DYN_M" not in (st.matched_levels or []) and "DYN_W" not in (st.matched_levels or [])):
                vol_sma = statistics.fmean([x.v for x in seq[-self.vol_sma_n-1:-1]])
                mult = vol_round_mult_eff if (st.matched_count or 0) < 2 else max(0.85, vol_round_mult_eff - 0.25)
                vol_ok_round = (last.v >= mult * vol_sma) if vol_sma else True
            # disable pure SWING without confluence
            if self.disable_swing_without_conf and (st.level_type in ("SWING_H","SWING_L")) and (st.matched_count or 0) < 2:
                self._stat('swing_no_conf')
                self._debug_reject(key, st, last, 'swing_no_conf', matched=st.matched_count)
                return
            # session filter (UTC hours)
            if False and self.active_hours is not None:
                try:
                    h = datetime.utcfromtimestamp(int(last.ts_close)/1000).hour
                    if not (self.active_hours[0] <= h <= self.active_hours[1]):
                        self._stat('session_blocked')
                        self._debug_reject(key, st, last, 'session_blocked', hour=h, active=f"{self.active_hours[0]}-{self.active_hours[1]}")
                        return
                except Exception:
                    pass
            # minimum stop (in ticks) -- за главный хай/лоу
            tick = self._tick_for_symbol(key[0])
            ref_hi = st.fix_high if st.fix_high is not None else last.h
            est_sl = ref_hi + stop_offset_ticks_eff * tick  # strictly beyond main high
            stop_ticks = max(0.0, (est_sl - last.l) / tick)
            # dynamic minimum based on short-range (impulse short SMA)
            min_stop_ticks_dyn = max(int(self.min_stop_ticks), int(math.ceil((self.min_stop_alpha or 0.0) * max(_imp.get("short", 0.0), 0.0) / max(tick, 1e-9))))
            threshold_ticks = max(1, int(min_stop_ticks_dyn * 0.5))
            # Defer stats/logs until an actual break attempt
            impulse_blocked = not (rng_ok or rng_alt_ok)
            round_vol_blocked = not vol_ok_round
            # keep hard_stop_fail as computed above
            hard_stop_fail = (stop_ticks < threshold_ticks)
            # Шорт: считаем пробой по Low свечи
            break_low = (st.fix_low is not None and last.l <= st.fix_low * (1 - self.zone_eps))
            break_close = (st.fix_low is not None and last.c <= st.fix_low * (1 - self.zone_eps * 0.5))
            break_condition = bool(break_low or break_close)
            # Count failures only when there is an actual break attempt
            if break_condition:
                if impulse_blocked:
                    self._stat('impulse_fail')
                    self._debug_reject(
                        key, st, last, 'impulse_fail', last_range=(last.h - last.l), short_sma=_imp['short'], long_sma=_imp['long'], k=_imp['k'], threshold=_imp['threshold']
                    )
                if round_vol_blocked:
                    self._stat('round_vol_fail')
                    try:
                        vol_sma = statistics.fmean([x.v for x in seq[-self.vol_sma_n-1:-1]])
                    except Exception:
                        vol_sma = 0.0
                    self._debug_reject(key, st, last, 'round_vol_fail', last_v=last.v, vol_sma=vol_sma, mult=self.vol_round_mult)
                if hard_stop_fail:
                    self._stat('stop_too_small')
                    tick = self._tick_for_symbol(key[0])
                    self._debug_reject(
                        key, st, last, 'stop_too_small', stop_ticks=round(stop_ticks,3),
                        min_ticks=threshold_ticks, est_sl=round(est_sl,5), tick=tick
                    )
            mode = self._entry_mode_for(st, "short")
            if mode == "break":
                if break_condition and (rng_ok or rng_alt_ok) and vol_ok_round:
                    self._stat('ok_short')
                    print(f"[FPF] {key} BREAK DOWN below FIX_LOW={st.fix_low} on low={last.l} (ts_close={last.ts_close})")
                    self._emit_signal(key, direction="short", break_price=last.l, break_ts=last.ts_close)
                    self._reset_state(st, preserve_last_signal_ts=last.ts_close)
            elif mode == "retest1":
                if break_condition and (rng_ok or rng_alt_ok) and vol_ok_round:
                    st.stage = "await_retest_short"
                    st.pending_break_ts = last.ts_close
                    st.pending_break_price = last.l
                    return
        elif st.stage == "await_retest_short":
            # Wait for one retest candle: high returns to near fix_low, close confirms break
            eps_abs = abs((st.level_price or st.fix_high or last.h)) * self.eps_touch_pct * self._eps_mult_for(st.level_type or "ROUND")
            if st.fix_low is not None and last.h >= (st.fix_low - eps_abs) and last.c <= st.fix_low * (1 - self.zone_eps):
                self._stat('ok_short')
                print(f"[FPF] {key} RETESTED short after break below FIX_LOW={st.fix_low} on low={last.l} (ts_close={last.ts_close})")
                self._emit_signal(key, direction="short", break_price=last.l, break_ts=last.ts_close)
                self._reset_state(st, preserve_last_signal_ts=last.ts_close)
        elif st.stage == "returned_long":
            seq = list(buf)
            ranges = [x.h - x.l for x in seq]
            k_adj = 0.0
            if st.level_type == "ROUND" and self.require_conf_for_round and (st.matched_count or 0) < 2:
                k_adj += self.range_k_round_bonus
            k_base = range_k_base_eff + k_adj
            if (st.matched_count or 0) >= 2:
                k_base = max(1.0, k_base - 0.25)
            # If dynamic monthly/weekly is part of confluence, allow a bit softer k
            try:
                if any(t in (st.matched_levels or []) for t in ("DYN_M","DYN_W")):
                    k_base = max(1.0, k_base - 0.08)
            except Exception:
                pass
            _imp = self._impulse_metrics(ranges[:-1], (last.h - last.l), k_base=k_base)
            rng_ok = (last.h - last.l) >= _imp["threshold"]
            # Alternative impulse pass: near-threshold + (volume boost or confluence)
            rng_alt_ok = False
            if len(seq) > self.vol_sma_n:
                vol_sma_last = statistics.fmean([x.v for x in seq[-self.vol_sma_n-1:-1]])
                vol_boost = (last.v >= alt_vol_boost_eff * vol_sma_last) if vol_sma_last else True
            else:
                vol_boost = True
            conf_boost = (st.matched_count or 0) >= 2
            near_threshold = (last.h - last.l) >= alt_imp_near_eff * _imp["threshold"]
            rng_alt_ok = bool(near_threshold and (vol_boost or conf_boost))
            vol_ok_round = True
            if st.level_type == "ROUND" and len(seq) > self.vol_sma_n and ("DYN_M" not in (st.matched_levels or []) and "DYN_W" not in (st.matched_levels or [])):
                vol_sma = statistics.fmean([x.v for x in seq[-self.vol_sma_n-1:-1]])
                mult = vol_round_mult_eff if (st.matched_count or 0) < 2 else max(0.85, vol_round_mult_eff - 0.25)
                vol_ok_round = (last.v >= mult * vol_sma) if vol_sma else True
            # Defer stats/logs until an actual break attempt
            impulse_blocked = not (rng_ok or rng_alt_ok)
            round_vol_blocked = not vol_ok_round
            # keep hard_stop_fail as computed above
            if self.disable_swing_without_conf and (st.level_type in ("SWING_H","SWING_L")) and (st.matched_count or 0) < 2:
                self._stat('swing_no_conf')
                self._debug_reject(key, st, last, 'swing_no_conf', matched=st.matched_count)
                return
            if False and self.active_hours is not None:
                try:
                    h = datetime.utcfromtimestamp(int(last.ts_close)/1000).hour
                    if not (self.active_hours[0] <= h <= self.active_hours[1]):
                        self._stat('session_blocked')
                        self._debug_reject(key, st, last, 'session_blocked', hour=h, active=f"{self.active_hours[0]}-{self.active_hours[1]}")
                        return
                except Exception:
                    pass
            tick = self._tick_for_symbol(key[0])
            ref_lo = st.fix_low if st.fix_low is not None else last.l
            est_sl = ref_lo - stop_offset_ticks_eff * tick  # strictly beyond main low
            stop_ticks = max(0.0, (last.h - est_sl) / tick)
            min_stop_ticks_dyn = max(int(self.min_stop_ticks), int(math.ceil((self.min_stop_alpha or 0.0) * max(_imp.get("short", 0.0), 0.0) / max(tick, 1e-9))))
            threshold_ticks = max(1, int(min_stop_ticks_dyn * 0.5))
            hard_stop_fail = (stop_ticks < threshold_ticks)
            break_up = (st.fix_high is not None and last.h >= st.fix_high * (1 + self.zone_eps))
            break_close = (st.fix_high is not None and last.c >= st.fix_high * (1 + self.zone_eps * 0.5))
            break_condition = bool(break_up or break_close)
            # Count failures only when there is an actual break attempt
            if break_condition:
                if impulse_blocked:
                    self._stat('impulse_fail')
                    self._debug_reject(
                        key, st, last, 'impulse_fail', last_range=(last.h - last.l), short_sma=_imp['short'], long_sma=_imp['long'], k=_imp['k'], threshold=_imp['threshold']
                    )
                if round_vol_blocked:
                    self._stat('round_vol_fail')
                    try:
                        vol_sma = statistics.fmean([x.v for x in seq[-self.vol_sma_n-1:-1]])
                    except Exception:
                        vol_sma = 0.0
                    self._debug_reject(key, st, last, 'round_vol_fail', last_v=last.v, vol_sma=vol_sma, mult=self.vol_round_mult)
                if hard_stop_fail:
                    self._stat('stop_too_small')
                    tick = self._tick_for_symbol(key[0])
                    self._debug_reject(
                        key, st, last, 'stop_too_small', stop_ticks=round(stop_ticks,3),
                        min_ticks=threshold_ticks, est_sl=round(est_sl,5), tick=tick
                    )
            mode = self._entry_mode_for(st, "long")
            if mode == "break":
                if break_condition and (rng_ok or rng_alt_ok) and vol_ok_round:
                    self._stat('ok_long')
                    print(f"[FPF] {key} BREAK UP above FIX_HIGH={st.fix_high} on high={last.h} (ts_close={last.ts_close})")
                    self._emit_signal(key, direction="long", break_price=last.h, break_ts=last.ts_close)
                    self._reset_state(st, preserve_last_signal_ts=last.ts_close)
            elif mode == "retest1":
                if break_condition and (rng_ok or rng_alt_ok) and vol_ok_round:
                    st.stage = "await_retest_long"
                    st.pending_break_ts = last.ts_close
                    st.pending_break_price = last.h
                    return
        elif st.stage == "await_retest_long":
            # Wait for one retest candle: low returns to near fix_high, close confirms break
            eps_abs = abs((st.level_price or st.fix_low or last.l)) * self.eps_touch_pct * self._eps_mult_for(st.level_type or "ROUND")
            if st.fix_high is not None and last.l <= (st.fix_high + eps_abs) and last.c >= st.fix_high * (1 + self.zone_eps):
                self._stat('ok_long')
                print(f"[FPF] {key} RETESTED long after break above FIX_HIGH={st.fix_high} on high={last.h} (ts_close={last.ts_close})")
                self._emit_signal(key, direction="long", break_price=last.h, break_ts=last.ts_close)
                self._reset_state(st, preserve_last_signal_ts=last.ts_close)

    def _reset_state(self, st: FixState, preserve_last_signal_ts: Optional[int] = None):
        st.fix_high = None
        st.fix_low = None
        st.fix_high_ts = None
        st.fix_low_ts = None
        st.return_ts = None
        st.vol_fix = None
        st.level_type = None
        st.level_price = None
        st.level_meta = None
        st.stage = "idle"
        st.last_signal_fix_ts = preserve_last_signal_ts
        st.pending_break_ts = None
        st.pending_break_price = None

    def _pick_level(self, price: float, levels: Optional[List[dict]]) -> Tuple[Optional[str], Optional[float], Optional[dict], List[str]]:
        """Pick best level by priority if within eps; also return a list of all types that are within their eps (confluence)."""
        if not levels:
            return None, None, None, []
        # index by type (keep best by heat)
        best: Dict[str, dict] = {}
        for it in levels:
            lt = str(it.get("type", "")); L = it.get("price"); meta = it.get("meta") if isinstance(it.get("meta"), dict) else None
            if lt == "" or L is None:
                continue
            heat = float(meta.get("heat", 0.0)) if meta else 0.0
            prev = best.get(lt)
            if prev is None or float((prev.get("meta") or {}).get("heat", 0.0)) < heat:
                best[lt] = {"type": lt, "price": float(L), "meta": meta}
        # find best by priority
        chosen = None
        for lt in self.level_priority:
            it = best.get(lt)
            if not it:
                continue
            L = float(it["price"])
            mult = self._eps_mult_for(lt)
            eps_abs = abs(L) * self.eps_touch_pct * mult
            if abs(price - L) <= eps_abs:
                chosen = (lt, L, (it.get("meta") if isinstance(it.get("meta"), dict) else None))
                break
        if not chosen:
            return None, None, None, []
        # compute confluence: other types also within their eps
        matched: List[str] = []
        for lt, it in best.items():
            L = float(it["price"])
            mult = self._eps_mult_for(lt)
            eps_abs = abs(L) * self.eps_touch_pct * mult
            if abs(price - L) <= eps_abs:
                matched.append(lt)
        return chosen[0], chosen[1], chosen[2], matched

    def _near_level(self, price: float, level_type: Optional[str], level_price: Optional[float]) -> bool:
        if not level_type or level_price is None:
            return True
        eps_abs = abs(level_price) * self.eps_touch_pct * self._eps_mult_for(level_type)
        return abs(price - level_price) <= eps_abs

    def _impulse_metrics(self, recent_ranges: List[float], last_range: float, k_base: Optional[float] = None) -> dict:
        """Return diagnostic metrics used by impulse check."""
        if not recent_ranges:
            return {"short": 0.0, "long": 0.0, "k": (self.range_k_base if k_base is None else k_base), "threshold": 0.0}
        short = statistics.fmean(recent_ranges[-14:]) if len(recent_ranges) >= 5 else statistics.fmean(recent_ranges)
        long = statistics.fmean(recent_ranges[-100:]) if len(recent_ranges) >= 20 else short
        k = self.range_k_base if k_base is None else k_base
        if short < 0.8 * long:
            k += 0.02
        elif short > 1.2 * long:
            k = max(1.0, k - 0.25)
        threshold = k * short
        return {"short": short, "long": long, "k": k, "threshold": threshold}

    def _impulse_ok(self, recent_ranges: List[float], last_range: float, k_base: Optional[float] = None) -> bool:
        """ATR-adaptive range expansion check: compare last_range to short SMA adjusted by regime."""
        metrics = self._impulse_metrics(recent_ranges, last_range, k_base=k_base)
        return last_range >= metrics["threshold"]

    def _emit_setup(self, key: Tuple[str,str], stage: str, price: float, ts: int):
        """
        Emit setup event (FIX_HIGH / FIX_LOW / RETURN) through the main pipeline,
        with a payload similar to final signal schema.
        """
        try:
            symbol, tf = key
            tv_symbol = f"BINANCE:{symbol}.P"
            interval_map = {"1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30", "1h": "60", "4h": "240", "1d": "D"}
            interval = interval_map.get(tf, "60")
            t = int(ts) if ts is not None else None
            if t is None:
                return
            sig_tv = self._build_tv_url(symbol, tf, t)
            # Convert ts to seconds
            ts_sec = int(t // 1000) if t > 10_000_000_000 else t

            # Build a setup payload aligned with final signal schema
            st = self.states.get(key, FixState())
            ai = self._calc_ai_score(st.level_type, st.level_meta, None)
            sig = {
                "symbol": symbol,
                "tf": tf,
                "direction": "setup",
                "fix_high": st.fix_high,
                "fix_low": st.fix_low,
                "fix_high_ts": st.fix_high_ts,
                "fix_low_ts": st.fix_low_ts,
                "return_ts": st.return_ts,
                "ts": t,                 # moment of setup event
                "break_ts": None,        # no actual break yet
                "break_price": float(price) if price is not None else 0.0,
                "ai_score": ai,
                "strength_pct": int(self._calc_ai_score(st.level_type, st.level_meta, None)),
                "level_meta": st.level_meta,
                "tv_url": sig_tv,
                "note": f"SETUP: {stage}",
                "level_type": st.level_type,
                "level_price": st.level_price,
                "matched_levels": st.matched_levels,
                "conf_n": st.matched_count,
            }
            if stage == "FIX_HIGH":
                sig["fix_high_url"] = self._build_tv_url(symbol, tf, t)
            elif stage == "FIX_LOW":
                sig["fix_low_url"] = self._build_tv_url(symbol, tf, t)
            elif stage == "RETURN":
                sig["return_url"] = self._build_tv_url(symbol, tf, t)

            # Go through the main pipeline: SignalManager will fan out to ui.signal and storage
            self.bus.publish("signal.detected", sig)
        except Exception:
            pass

    def _emit_signal(self, key: Tuple[str,str], direction: str, break_price: float, break_ts: int):

        symbol, tf = key
        st = self.states[key]

        # Debounce: avoid duplicate signals for the same context within 5 minutes
        try:
            if st.last_signal_fix_ts is not None and abs(int(break_ts) - int(st.last_signal_fix_ts)) < 5 * 60 * 1000:
                return
        except Exception:
            pass

        # Decide which fix candle is the reference for entry
        if direction == "short":
            ts_fix = st.fix_low_ts or st.fix_high_ts or st.return_ts or break_ts
            fix_close = st.fix_low_close or st.fix_high_close or break_price
            prefix_low = st.fix_low if st.fix_low is not None else break_price
            prefix_high = st.fix_high if st.fix_high is not None else break_price
        else:  # long
            ts_fix = st.fix_high_ts or st.fix_low_ts or st.return_ts or break_ts
            fix_close = st.fix_high_close or st.fix_low_close or break_price
            prefix_low = st.fix_low if st.fix_low is not None else break_price
            prefix_high = st.fix_high if st.fix_high is not None else break_price

        fix_high_ts = st.fix_high_ts
        fix_low_ts = st.fix_low_ts
        return_ts = st.return_ts

        # Robust TradingView links anchored at event times
        tv_url_break = self._build_tv_url(symbol, tf, break_ts)
        tv_url_fix_high = self._build_tv_url(symbol, tf, fix_high_ts) if fix_high_ts else None
        tv_url_fix_low  = self._build_tv_url(symbol, tf, fix_low_ts) if fix_low_ts else None
        tv_url_return   = self._build_tv_url(symbol, tf, return_ts) if return_ts else None

        # Strength & grouping for de-dup and multi-TF aggregation
        base_strength = int(self._calc_ai_score(st.level_type, st.level_meta, direction))
        conf_bonus = min(12, 4 * max(0, int(st.matched_count or 0) - 1))
        strength_pct = int(max(1, min(100, base_strength + conf_bonus)))
        grp = self._group_id(symbol, tf, direction, st.level_price, ts_fix)

        ai = self._calc_ai_score(st.level_type, st.level_meta, direction)

        # --- zone_hint: compact hint for VAL/VAH/POC zone if available
        zone_hint = None
        try:
            lm = st.level_meta or {}
            poc = lm.get("poc_price") or lm.get("poc")
            val = lm.get("val")
            vah = lm.get("vah")
            if val is not None and vah is not None:
                zone_hint = {"low": float(val), "high": float(vah), "poc": (float(poc) if poc is not None else None)}
        except Exception:
            zone_hint = None

        sig = {
            "symbol": symbol,
            "tf": tf,
            "direction": direction,
            "fix_high": st.fix_high,
            "fix_low": st.fix_low,
            "fix_high_ts": fix_high_ts,
            "fix_low_ts": fix_low_ts,
            "return_ts": return_ts,
            "ts": int(break_ts) if break_ts is not None else None,
            "break_price": break_price,
            "ai_score": ai,
            "level_meta": st.level_meta,
            "tv_url": tv_url_break,
            "fix_high_url": tv_url_fix_high,
            "fix_low_url": tv_url_fix_low,
            "return_url": tv_url_return,
            "note": "FPF v1",
            "group_id": grp,
            "strength_pct": strength_pct,
            "level_type": st.level_type,
            "level_price": st.level_price,
            "matched_levels": st.matched_levels,
            "conf_n": st.matched_count,
            # ---- required for OutcomeTracker ----
            "ts_fix": int(ts_fix) if ts_fix is not None else None,
            "fix_close": float(fix_close) if fix_close is not None else None,
            "prefix_low": float(prefix_low) if prefix_low is not None else None,
            "prefix_high": float(prefix_high) if prefix_high is not None else None,
            "zone_hint": zone_hint,
            "no_reentry": True,
        }

        # Log for human-readable control
        try:
            human = datetime.fromtimestamp(int(break_ts) / 1000.0 if int(break_ts) > 10_000_000_000 else int(break_ts))
            print(f"[FPF] SIGNAL {symbol} {tf} {direction} at {break_price} ts={break_ts} ({human:%Y-%m-%d %H:%M:%S})")
        except Exception:
            print(f"[FPF] SIGNAL {symbol} {tf} {direction} at {break_price} ts={break_ts}")

        # Publish to the main bus; SignalManager will fan out (ui, storage, etc.)
        self.bus.publish("signal.detected", sig)

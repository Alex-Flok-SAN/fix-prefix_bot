# -*- coding: utf-8 -*-
"""
ai_search_pattern.py

State machine + utilities for detecting and describing the SHORT FIX→RAY→HI pattern→PREFIX→BA25→TP pattern.

This module is intentionally UI-agnostic:
- It consumes candles (ideally resampled to the chart timeframe) in chronological order.
- It emits a structured PatternResult (areas, rays, points, meta) that can be rendered by any UI.
- It supports stepwise operation so a GUI (like tools/tv_ingest_app.py) can drive it interactively.
- It stores "accept" flags for each stage to match the UX with mini checkmarks per element.

Dependencies: only stdlib. Pandas/numpy are deliberately not required here.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
@dataclass
class PatternConfig:
    tick_size: float = 0.01          # минимальный шаг цены (1 тик)
    epsilon: float = 1e-9            # численный допуск
    require_from_above: bool = True  # для валидации RAY (шорт)
    prefix_touch_from_below: bool = True  # для фиксации первого касания PREFIX снизу
from enum import Enum, auto
from typing import List, Optional, Dict, Any, Tuple
import json
import math

# Custom exceptions for clearer upstream handling
class PatternError(Exception):
    pass

class IncompleteStageError(PatternError):
    pass

Price = float


# ---------------------------
# Basic candle type (lightweight)
# ---------------------------

@dataclass(frozen=True)
class Candle:
    ts_open_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    ts_close_ms: int


# ---------------------------
# Geometry/Annotation types
# ---------------------------

@dataclass
class Rect:  # area like FIX / PREFIX / TP rectangles
    left_ts: int
    right_ts: int
    top: float
    bottom: float
    label: str = ""
    accepted: bool = False  # mini checkbox flag

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Ray:  # baseline like RAY (horizontal), BA25 (horizontal)
    ts_start: int
    price: float
    ts_end: Optional[int] = None  # when validated or touched
    label: str = ""
    accepted: bool = False
    touch_ts: Optional[int] = None  # when price first touched/updated
    touch_price: Optional[float] = None
    anchor_low_idx: Optional[int] = None  # index of candle whose low this ray is anchored to

    def is_active(self) -> bool:
        return self.ts_end is None

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Mark:  # single point markers like HI apex or RAY touch diamond
    ts: int
    price: float
    label: str = ""

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------
# FSM States
# ---------------------------

class PatternStage(Enum):
    INIT = auto()
    FIX = auto()
    RAY = auto()
    HI = auto()
    PREFIX = auto()
    BA25 = auto()
    TP = auto()
    DONE = auto()


# ---------------------------
# Meta and Result containers
# ---------------------------

@dataclass
class PatternMeta:
    """Pattern metadata and metrics."""
    symbol: str
    tf_minutes: int
    direction: str = "short"  # we focus short pattern now
    fix_to_hi_gap: Optional[float] = None  # vertical gap between FIX top and HI apex
    notes: Dict[str, Any] = field(default_factory=dict)  # any additional notes

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class PatternResult:
    meta: PatternMeta
    fix: Optional[Rect] = None
    ray: Optional[Ray] = None
    hi_pattern: Optional[Mark] = None
    prefix: Optional[Rect] = None
    ba25: Optional[Ray] = None
    flat: Optional[Rect] = None  # optional, managed by UI but kept here for JSON completeness
    tp_main: Optional[Rect] = None
    tp_low: List[Rect] = field(default_factory=list)
    tp_extra: List[Rect] = field(default_factory=list)  # e.g., TP1, TP2 small boxes
    take25_regions: List[Rect] = field(default_factory=list)  # 25% scale-out boxes

    # bookkeeping
    stage: PatternStage = PatternStage.INIT
    history: List[Dict[str, Any]] = field(default_factory=list)  # audit trail of transitions

    def to_json(self) -> str:
        payload = {
            "meta": self.meta.to_json(),
            "fix": self.fix.to_json() if self.fix else None,
            "ray": self.ray.to_json() if self.ray else None,
            "hi_pattern": self.hi_pattern.to_json() if self.hi_pattern else None,
            "prefix": self.prefix.to_json() if self.prefix else None,
            "ba25": self.ba25.to_json() if self.ba25 else None,
            "flat": self.flat.to_json() if self.flat else None,
            "tp_main": self.tp_main.to_json() if self.tp_main else None,
            "tp_low": [r.to_json() for r in self.tp_low],
            "tp_extra": [r.to_json() for r in self.tp_extra],
            "take25": [r.to_json() for r in self.take25_regions],
            "stage": self.stage.name,
            "history": self.history,
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def add_history(self, event: str, info: Dict[str, Any]) -> None:
        self.history.append({"event": event, "info": info})

    @classmethod
    def from_json(cls, s: str) -> "PatternResult":
        data = json.loads(s)
        meta = PatternMeta(**data["meta"]) if isinstance(data.get("meta"), dict) else data["meta"]
        def _rect(d):
            return Rect(**d) if d else None
        def _ray(d):
            return Ray(**d) if d else None
        def _mark(d):
            return Mark(**d) if d else None
        res = cls(
            meta=meta,
            fix=_rect(data.get("fix")),
            ray=_ray(data.get("ray")),
            hi_pattern=_mark(data.get("hi_pattern")),
            prefix=_rect(data.get("prefix")),
            ba25=_ray(data.get("ba25")),
            flat=_rect(data.get("flat")),
            tp_main=_rect(data.get("tp_main")),
            tp_low=[Rect(**r) for r in data.get("tp_low", [])],
            tp_extra=[Rect(**r) for r in data.get("tp_extra", [])],
            take25_regions=[Rect(**r) for r in data.get("take25", [])],
            stage=PatternStage[data.get("stage", "INIT")],
            history=data.get("history", []),
        )
        return res


# ---------------------------
# Utility helpers
# ---------------------------

def _clamp(a: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, a))

def _price_mid(a: float, b: float) -> float:
    return (a + b) / 2.0

def _ts_mid(a: int, b: int) -> int:
    return (a + b) // 2


# --- FIX suggestion helper ---
def suggest_fix_bounds(candles: List["Candle"], left_ts: int, right_ts: int, side_bars: int = 3, top_pad: float = 0.05) -> Tuple[int, int, Price, Price]:
    """Return (left_ts, right_ts, top, bottom) for FIX built as a *plateau* of highs.

    Rules (UI-agnostic, stdlib only):
    - Work on candles inside [left_ts, right_ts], expanded by `side_bars` on each side for context.
    - Define a reference top as the median of the top-N highs (N scales with segment length).
    - Keep only candles whose highs lie within a small band below that reference top (dense plateau).
    - Choose the *best contiguous block* among qualified indices (longest, then highest mean high).
    - Trim impulse edge bars: if an edge bar is a lone spike (very large range) or too far below the ref, drop it.
    - The FIX box hugs the plateau: top = block_max_high + pad, bottom = min low within block.
    """
    if not candles:
        raise PatternError("No candles provided for FIX suggestion")
    # collect indices inside range
    idxs = [i for i, c in enumerate(candles) if left_ts <= c.ts_close_ms <= right_ts]
    if not idxs:
        raise PatternError("No candles in the requested FIX range")
    i0, i1 = idxs[0], idxs[-1]
    i0 = max(0, i0 - side_bars)
    i1 = min(len(candles) - 1, i1 + side_bars)
    seg = candles[i0:i1 + 1]
    if not seg:
        raise PatternError("Empty segment for FIX suggestion")

    # helpers (stdlib only)
    def _percentile(vals, q: float):
        if not vals:
            return None
        s = sorted(vals)
        k = (len(s) - 1) * q
        f = int(math.floor(k))
        c = int(math.ceil(k))
        if f == c:
            return s[f]
        return s[f] + (s[c] - s[f]) * (k - f)

    def _median(vals):
        s = sorted(vals)
        n = len(s)
        if n == 0:
            return None
        m = n // 2
        if n % 2:
            return s[m]
        return (s[m-1] + s[m]) / 2.0

    highs = [c.high for c in seg]
    lows  = [c.low  for c in seg]
    ranges = [max(1e-12, h - l) for h, l in zip(highs, lows)]
    # Compute how close candle bodies are to the highs
    opens  = [c.open for c in seg]
    closes = [c.close for c in seg]
    body_to_high = [h - max(o, cl) for h, o, cl in zip(highs, opens, closes)]  # distance of body top to high

    max_h, min_l = max(highs), min(lows)
    height_seg = max(1e-9, max_h - min_l)

    # Reference top: tighter of two measures — 90th percentile or median of top-N highs
    n = len(seg)
    top_n = max(3, min(12, n // 8))
    top_sorted = sorted(highs, reverse=True)[:top_n]
    ref_top_topN = _median(top_sorted) if top_sorted else max_h
    ref_top_p90 = _percentile(highs, 0.90) or max_h
    ref_top = max(ref_top_p90, ref_top_topN)

    # Robust band using MAD (median absolute deviation) and a floor by 1% of segment height
    med_h = _median(highs) or ref_top
    mad = _median([abs(h - med_h) for h in highs]) or 0.0
    band = max(0.01 * height_seg, 1.2 * mad)

    # Spike/impulse thresholds from ranges
    p70_rng = _percentile(ranges, 0.70) or (height_seg * 0.08)
    p75_rng = _percentile(ranges, 0.75) or (height_seg * 0.1)
    p90_rng = _percentile(ranges, 0.90) or (height_seg * 0.2)

    # --- Apex-centered plateau (ultra tight) ---
    # 1) Find absolute apex high inside the segment
    apex_idx_local = max(range(len(highs)), key=lambda k: highs[k])
    apex_high = highs[apex_idx_local]
    
    # 2) Tight delta around apex and stricter impulse/body thresholds
    delta = max(0.0075 * height_seg, 0.8 * mad)  # ~0.75% of segment height or 0.8×MAD
    p65_rng = _percentile(ranges, 0.65) or (height_seg * 0.07)
    
    # 3) Build list of indices that qualify for the apex plateau
    ok_idxs = []
    for j in range(len(highs)):
        h = highs[j]
        r = ranges[j]
        b2h = body_to_high[j]
        close_to_apex = (h >= apex_high - delta)
        not_impulse   = (r <= p65_rng * 1.05)
        body_near_hi  = (r <= 0) or (b2h <= 0.25 * r)
        if close_to_apex and not_impulse and body_near_hi:
            ok_idxs.append(j)
    if not ok_idxs:
        ok_idxs = [apex_idx_local]

    # 4) From ok indices, extract the longest consecutive block; if tie, choose the one closest to the apex
    blocks = []  # (li, ri)
    start = ok_idxs[0]
    prev = start
    for j in ok_idxs[1:]:
        if j == prev + 1:
            prev = j
        else:
            blocks.append((start, prev))
            start = j
            prev = j
    blocks.append((start, prev))

    # choose best block
    def _block_score(li, ri):
        length = ri - li + 1
        center = (li + ri) / 2.0
        dist_to_apex = abs(center - apex_idx_local)
        return (length, -dist_to_apex)
    li_loc, ri_loc = max(blocks, key=lambda t: _block_score(t[0], t[1]))

    # 5) Edge trimming with even stricter rules to cut off entry/exit spikes
    def _edge_bad(idx_local: int) -> bool:
        h = highs[idx_local]
        r = ranges[idx_local]
        b2h = body_to_high[idx_local]
        too_spiky = (r > p65_rng * 1.05)  # even tighter on edges
        too_low   = h < (apex_high - 0.6 * delta)
        body_bad  = (r > 0) and (b2h > 0.25 * r)
        return too_spiky or too_low or body_bad

    while (ri_loc - li_loc + 1) > 2 and _edge_bad(li_loc):
        li_loc += 1
    while (ri_loc - li_loc + 1) > 2 and _edge_bad(ri_loc):
        ri_loc -= 1

    # 6) Enforce minimal width of two bars (extend to nearest neighbor if needed)
    if (ri_loc - li_loc + 1) < 2:
        if ri_loc + 1 < len(highs):
            ri_loc = ri_loc + 1
        elif li_loc - 1 >= 0:
            li_loc = li_loc - 1

    # Convert local indices back to global
    li = i0 + li_loc
    ri = i0 + ri_loc

    block_high = max(highs[li_loc:ri_loc + 1])
    block_low  = min(lows[li_loc:ri_loc + 1])
    height_block = max(1e-9, block_high - block_low)

    top = block_high + 0.008 * height_block  # apex-hugging: 0.8% of block height
    bottom = block_low

    return (candles[li].ts_close_ms, candles[ri].ts_close_ms, top, bottom)


# ---------------------------
# Pattern State Machine
# ---------------------------

class PatternStateMachine:
    """
    Deterministic state machine implementing SHORT pattern:

        1. FIX area confirmed by user (accepted=True).
        2. RAY baseline from the nearest local low AFTER FIX and BEFORE HI.
        3. HI apex (max high between that low and a later low prior to PREFIX).
        4. PREFIX area aligned with FIX vertically, starts at RAY touch to the screen right.
        5. BA25 baseline drawn from a previous low once price tags PREFIX, used for BE+25%.
        6. TP areas are user-driven; TP_main may be auto-proposed after PREFIX touch.

    The FSM is tolerant: it allows external (UI) edits via setter methods that set/accept elements,
    and internal streaming via feed(candle) that automatically advances the pattern where possible.
    """

    def __init__(self, meta: PatternMeta, cfg: Optional["PatternConfig"] = None):
        self.result = PatternResult(meta=meta)
        self.cfg = cfg or PatternConfig()
        # caches
        self._candles: List[Candle] = []
        self._last_ts: Optional[int] = None
        # indices of interest for automatic search
        self._fix_end_ts: Optional[int] = None  # right boundary of FIX by ts
        self._post_fix_low_idx: Optional[int] = None
        self._hi_search_active: bool = False
        self._prev_candle: Optional[Candle] = None
        self._prefix_first_touch_ts: Optional[int] = None

    # ---- internal index helpers ----
    def _index_closest_by_ts(self, ts_hint: int) -> Optional[int]:
        if not self._candles:
            return None
        return min(range(len(self._candles)), key=lambda i: abs(self._candles[i].ts_close_ms - ts_hint))

    def _snap_to_candle_low(self, ts_hint: int, price_hint: float, window: int = 5) -> Optional[Tuple[int, float, int]]:
        """Return (ts_close_ms, low, idx) of the lowest-low candle within +/- window bars around closest ts."""
        if not self._candles:
            return None
        ci = self._index_closest_by_ts(ts_hint)
        if ci is None:
            return None
        lo = max(0, ci - window)
        hi = min(len(self._candles) - 1, ci + window)
        seg = self._candles[lo:hi+1]
        if not seg:
            return None
        # pick the minimum low; if ties, pick the one closest to ts_hint
        min_low = min(x.low for x in seg)
        candidates = [k for k in range(lo, hi+1) if self._candles[k].low == min_low]
        best = min(candidates, key=lambda k: abs(self._candles[k].ts_close_ms - ts_hint))
        c = self._candles[best]
        return (c.ts_close_ms, c.low, best)

    # ---- Snapping helpers for UI (snap to candle lows) ----
    def snap_low_near_ts(self, ts_hint: int, window: int = 5) -> Optional[Tuple[int, Price]]:
        """Return (ts_close_ms, low) for candle whose ts is closest to ts_hint within +/- `window` bars, preferentially the minimum low.
        """
        if not self._candles:
            return None
        # find index closest to ts_hint
        closest = min(range(len(self._candles)), key=lambda i: abs(self._candles[i].ts_close_ms - ts_hint))
        lo = max(0, closest - window)
        hi = min(len(self._candles)-1, closest + window)
        segment = self._candles[lo:hi+1]
        if not segment:
            return None
        cand = min(segment, key=lambda c: c.low)
        return (cand.ts_close_ms, cand.low)

    def snap_ray_to_low(self, ts_hint: int) -> Optional[Ray]:
        out = self.snap_low_near_ts(ts_hint)
        if out is None:
            return None
        ts, price = out
        self.set_ray_from_low(ts_start=ts, price=price, accept=False)
        return self.result.ray

    def snap_ba25_to_low(self, ts_left: int, ts_right: int) -> Optional[Ray]:
        """Pick last local low between bounds and set BA25."""
        j = self._find_last_local_low_between(ts_left, ts_right)
        if j is None:
            return None
        c = self._candles[j]
        self.set_ba25(ts_start=c.ts_close_ms, price=c.low, accept=False)
        return self.result.ba25


    # ---- public snapping for existing rays (used by UI dragging) ----
    def move_ray_to_ts_hint(self, ts_hint: int) -> Optional[Ray]:
        if self.result.ray is None:
            return None
        anchor = self._snap_to_candle_low(ts_hint, self.result.ray.price)
        if anchor is None:
            return None
        ts, low, idx = anchor
        self.result.ray.ts_start = ts
        self.result.ray.price = low
        self.result.ray.anchor_low_idx = idx
        self.result.add_history("move_ray_snap", {"ts": ts, "low": low})
        return self.result.ray

    def move_ba25_to_ts_hint(self, ts_hint: int) -> Optional[Ray]:
        if self.result.ba25 is None:
            return None
        anchor = self._snap_to_candle_low(ts_hint, self.result.ba25.price)
        if anchor is None:
            return None
        ts, low, idx = anchor
        self.result.ba25.ts_start = ts
        self.result.ba25.price = low
        self.result.ba25.anchor_low_idx = idx
        self.result.add_history("move_ba25_snap", {"ts": ts, "low": low})
        return self.result.ba25

    # --------- Public API ---------

    def reset(self) -> None:
        meta = self.result.meta
        self.__init__(meta)

    def set_fix(self, left_ts: int, right_ts: int, top: float, bottom: float, accept: bool = False) -> None:
        """Called by UI right after the user draws/accepts FIX."""
        self.result.fix = Rect(left_ts, right_ts, top, bottom, label="FIX", accepted=accept)
        self._fix_end_ts = right_ts
        self.result.stage = PatternStage.FIX
        self.result.add_history("set_fix", {"left_ts": left_ts, "right_ts": right_ts, "top": top, "bottom": bottom})

    def accept_fix(self) -> None:
        if self.result.fix:
            self.result.fix.accepted = True
            self.result.stage = PatternStage.RAY
            self.result.add_history("accept_fix", {})

    def set_ray_from_low(self, ts_start: int, price: float, accept: bool = False) -> None:
        """UI can pick a specific low; the ray is horizontal at that low price."""
        anchor = self._snap_to_candle_low(ts_start, price)
        if anchor is not None:
            ts_start, price, idx = anchor
            self.result.ray = Ray(ts_start=ts_start, price=price, label="RAY", accepted=accept, anchor_low_idx=idx)
        else:
            self.result.ray = Ray(ts_start=ts_start, price=price, label="RAY", accepted=accept)
        self.result.stage = PatternStage.RAY
        self.result.add_history("set_ray", {"ts_start": ts_start, "price": price, "snapped": anchor is not None})

    def set_hi_pattern(self, ts: int, price: float, accept: bool = False) -> None:
        self.result.hi_pattern = Mark(ts=ts, price=price, label="HI_PATTERN")
        if self.result.fix:
            self.result.meta.fix_to_hi_gap = float(max(0.0, price - self.result.fix.top))
        if accept:
            # advance to PREFIX suggestions
            self.result.stage = PatternStage.PREFIX
        self.result.add_history("set_hi_pattern", {"ts": ts, "price": price, "accept": accept})

    def set_prefix(self, left_ts: int, right_ts: int, top: float, bottom: float, accept: bool = False) -> None:
        self.result.prefix = Rect(left_ts, right_ts, top, bottom, label="PREFIX", accepted=accept)
        self.result.stage = PatternStage.PREFIX
        self.result.add_history("set_prefix", {"left_ts": left_ts, "right_ts": right_ts, "top": top, "bottom": bottom})

    def propose_prefix_from_touch(self, touch_ts: int) -> Rect:
        fx = self.result.fix
        if not fx:
            raise IncompleteStageError("Cannot propose PREFIX without FIX")
        # left edge at touch, right is initially equal (UI will extend to screen-right)
        r = Rect(left_ts=touch_ts, right_ts=touch_ts, top=fx.top, bottom=fx.bottom, label="PREFIX", accepted=False)
        self.result.prefix = r
        self.result.stage = PatternStage.PREFIX
        self.result.add_history("propose_prefix", {"touch_ts": touch_ts})
        return r

    def set_ba25(self, ts_start: int, price: float, accept: bool = False) -> None:
        anchor = self._snap_to_candle_low(ts_start, price)
        if anchor is not None:
            ts_start, price, idx = anchor
            self.result.ba25 = Ray(ts_start=ts_start, price=price, label="BA25", accepted=accept, anchor_low_idx=idx)
        else:
            self.result.ba25 = Ray(ts_start=ts_start, price=price, label="BA25", accepted=accept)
        self.result.stage = PatternStage.BA25
        self.result.add_history("set_ba25", {"ts_start": ts_start, "price": price, "snapped": anchor is not None})

    def set_tp_main(self, left_ts: int, right_ts: int, top: float, bottom: float, accept: bool = False) -> None:
        self.result.tp_main = Rect(left_ts, right_ts, top, bottom, label="TP_MAIN", accepted=accept)
        self.result.stage = PatternStage.TP
        self.result.add_history("set_tp_main", {"left_ts": left_ts, "right_ts": right_ts, "top": top, "bottom": bottom})

    def add_tp_low(self, left_ts: int, right_ts: int, top: float, bottom: float, label: str = "TP_LOW") -> None:
        self.result.tp_low.append(Rect(left_ts, right_ts, top, bottom, label=label))
        self.result.add_history("add_tp_low", {"left_ts": left_ts, "right_ts": right_ts})

    def add_tp_extra(self, left_ts: int, right_ts: int, top: float, bottom: float, label: str = "TP1") -> None:
        self.result.tp_extra.append(Rect(left_ts, right_ts, top, bottom, label=label))
        self.result.add_history("add_tp_extra", {"left_ts": left_ts, "right_ts": right_ts, "label": label})

    def add_take25(self, left_ts: int, right_ts: int, top: float, bottom: float, label: str = "TAKE25") -> None:
        self.result.take25_regions.append(Rect(left_ts, right_ts, top, bottom, label=label))
        self.result.add_history("add_take25", {"left_ts": left_ts, "right_ts": right_ts, "label": label})

    def export_json(self) -> str:
        return self.result.to_json()

    # --------- Streaming API ---------

    def feed(self, c: Candle) -> None:
        """
        Feed candles chronologically; the FSM will:
        - locate the post-FIX low and cast RAY (if FIX is accepted and RAY not set),
        - check for RAY touch from above to validate FIX→PREFIX,
        - track HI apex (max high between post-fix low and the low prior to PREFIX),
        - create PREFIX proposal once RAY is touched.
        """
        self._prev_candle = self._candles[-1] if self._candles else None
        self._candles.append(c)
        self._last_ts = c.ts_close_ms

        if self.result.stage in (PatternStage.INIT,):
            return

        if self.result.stage in (PatternStage.FIX, PatternStage.RAY, PatternStage.HI, PatternStage.PREFIX):
            self._auto_progress_short(c)
            self._maybe_handle_prefix_first_touch(c)

        if self.result.stage in (PatternStage.BA25, PatternStage.TP):
            # BA25/TP tracking could be added here if needed
            pass

    # --------- Internal mechanics ---------

    def _auto_progress_short(self, c: Candle) -> None:
        """
        Implements the short pattern rules in a tolerant way per the user's spec:
        - After FIX accepted: find local low after FIX such that a subsequent HI pattern forms above FIX -> start RAY from that low.
        - HI pattern is the highest high between that low and a later low prior to PREFIX.
        - When price (from above) *strictly updates* (not just touches) the RAY low: validate FIX-PREFIX, set RAY touch (record actual touch low),
          and propose PREFIX area aligned with FIX (same vertical bounds), left at touch ts,
          and right pushed to "screen right" (we don't know UI width here, so keep None; UI can clamp).
        The BA25 baseline is anchored within a window after HI and before PREFIX.
        """
        # Need accepted FIX first
        fx = self.result.fix
        if not fx or not fx.accepted:
            return

        # 1) If we have no RAY yet: try to find a suitable post-FIX low with a HI pattern above FIX
        if self.result.ray is None:
            low_idx = self._find_ray_low_after_fix_with_hi(fx)
            if low_idx is not None:
                low_c = self._candles[low_idx]
                self.set_ray_from_low(ts_start=low_c.ts_close_ms, price=low_c.low, accept=False)
                self._post_fix_low_idx = low_idx
                self._hi_search_active = True
                self.result.add_history("auto_set_ray", {"ts_start": low_c.ts_close_ms, "price": low_c.low})

        # 2) If RAY exists and HI pattern is not fixed yet: track HI pattern between post-fix low and current candle
        ray = self.result.ray
        if ray and self._hi_search_active and self.result.hi_pattern is None:
            try:
                start_i = self._post_fix_low_idx + 1 if self._post_fix_low_idx is not None else 0
                if start_i < len(self._candles):
                    window = self._candles[start_i:]
                    hi_c = max(window, key=lambda cc: cc.high)
                    self.set_hi_pattern(ts=hi_c.ts_close_ms, price=hi_c.high, accept=False)
            except Exception:
                pass  # keep tolerant

        # 3) Validate RAY update (strictly breaks the low by >= 1 tick) and from above (for short)
        if ray and ray.is_active():
            eps = self.cfg.epsilon
            broke_by_tick = (c.low <= (ray.price - (self.cfg.tick_size - eps)))
            from_above = (c.open > ray.price + eps and c.high > ray.price + eps) if self.cfg.require_from_above else True
            if broke_by_tick and from_above:
                ray.ts_end = c.ts_close_ms
                ray.touch_ts = c.ts_close_ms
                ray.touch_price = c.low
                self.result.add_history("ray_touched", {"ts": c.ts_close_ms, "ray_price": ray.price, "touch_price": c.low})
                # Propose PREFIX aligned with FIX. BA25 будет ставиться позже — при первом касании PREFIX.
                left_ts = c.ts_close_ms
                self.propose_prefix_from_touch(left_ts)
                self.result.stage = PatternStage.PREFIX


    def _maybe_handle_prefix_first_touch(self, c: Candle) -> None:
        """Detect first touch of PREFIX (from below, for short) and place BA25 only then.
        BA25 anchors at the last local low strictly between HI.ts and this touch candle.ts.
        """
        if self.result.prefix is None or self._prefix_first_touch_ts is not None:
            return
        fx = self.result.fix
        pr = self.result.prefix
        if fx is None or not fx.accepted:
            return
        # Determine if candle approached from below and touched/entered prefix vertical band [bottom, top]
        eps = self.cfg.epsilon
        came_from_below = False
        if self._prev_candle is not None:
            prev = self._prev_candle
            came_from_below = (prev.close < pr.bottom - eps) or (prev.open < pr.bottom - eps)
        touches_band = (c.high >= pr.bottom - eps) and (c.low <= pr.top + eps)
        if self.cfg.prefix_touch_from_below and not came_from_below:
            return
        if touches_band:
            self._prefix_first_touch_ts = c.ts_close_ms
            self.result.add_history("prefix_touched", {"ts": c.ts_close_ms})
            # Place BA25 now (not earlier): last local low between HI and this touch
            hi = self.result.hi_pattern
            if hi is not None:
                j = self._find_last_local_low_between(hi.ts, c.ts_close_ms)
                if j is not None:
                    lw = self._candles[j]
                    self.set_ba25(ts_start=lw.ts_close_ms, price=lw.low, accept=False)
                    self.result.add_history("auto_set_ba25_on_prefix_touch", {"ts_start": lw.ts_close_ms, "price": lw.low})

    def _find_low_after_ts(self, ts: int) -> Optional[int]:
        """
        Return index of the nearest local low AFTER given ts.
        Local low = candle whose low is <= both neighbors' lows (simple 3-candle pivot).
        If not found, return the first candle after ts with the minimal low in the next N bars.
        """
        N = 20  # look-ahead window as a compromise; can be tuned
        idx_after = None
        for i, cc in enumerate(self._candles):
            if cc.ts_close_ms > ts:
                idx_after = i
                break
        if idx_after is None:
            return None

        # Scan for a pivot low
        for i in range(idx_after + 1, min(idx_after + N, len(self._candles)) - 1):
            a, b, d = self._candles[i - 1], self._candles[i], self._candles[i + 1]
            if b.low <= a.low and b.low <= d.low:
                return i

        # fallback: pick minimal low within window
        window = self._candles[idx_after:min(idx_after + N, len(self._candles))]
        if not window:
            return None
        min_low = min(window, key=lambda cc: cc.low).low
        for i in range(idx_after, idx_after + len(window)):
            if math.isclose(self._candles[i].low, min_low) or self._candles[i].low == min_low:
                return i
        return None

    def _find_ray_low_after_fix_with_hi(self, fx: Rect, lookahead: int = 80) -> Optional[int]:
        """Return index of a local low after FIX for which, within the next `lookahead` bars,
        there exists a high strictly above FIX.top. Prefer the earliest such low.
        """
        # find first index after FIX
        start_idx = None
        for i, cc in enumerate(self._candles):
            if cc.ts_close_ms > fx.right_ts:
                start_idx = i
                break
        if start_idx is None:
            return None
        end_idx = min(len(self._candles), start_idx + lookahead)
        # scan for 3-candle pivot lows which lead to a hi above FIX
        for i in range(start_idx + 1, end_idx - 1):
            a, b, d = self._candles[i - 1], self._candles[i], self._candles[i + 1]
            if b.low <= a.low and b.low <= d.low:
                # look forward to see if any high exceeds FIX top
                fwd_window = self._candles[i+1:end_idx]
                if fwd_window and max(cc.high for cc in fwd_window) > fx.top:
                    return i
        # fallback: choose the minimum low in window which later sees a high above FIX
        if start_idx < end_idx:
            win = self._candles[start_idx:end_idx]
            min_low = min(win, key=lambda cc: cc.low).low
            for i in range(start_idx, end_idx):
                if self._candles[i].low == min_low:
                    # ensure later hi above FIX exists
                    fwd_window = self._candles[i+1:end_idx]
                    if fwd_window and max(cc.high for cc in fwd_window) > fx.top:
                        return i
        return None

    def _find_last_local_low_between(self, ts_left: int, ts_right: int) -> Optional[int]:
        """Return index of the latest 3-candle pivot low with ts in (ts_left, ts_right)."""
        idx = None
        for i in range(1, len(self._candles) - 1):
            c = self._candles[i]
            if not (ts_left < c.ts_close_ms < ts_right):
                continue
            a, b, d = self._candles[i - 1], c, self._candles[i + 1]
            if b.low <= a.low and b.low <= d.low:
                idx = i
        return idx

    def _index_after_ts(self, ts: int) -> Optional[int]:
        """Return the index of the first candle with ts_close_ms > ts, or None."""
        for i, cc in enumerate(self._candles):
            if cc.ts_close_ms > ts:
                return i
        return None

    def _highest_high_between(self, i0: int, i1: int) -> Optional[int]:
        """Return index of the candle with the highest high in [i0, i1]. If several, pick the last for stability."""
        n = len(self._candles)
        if n == 0:
            return None
        i0 = max(0, min(i0, n - 1))
        i1 = max(0, min(i1, n - 1))
        if i1 < i0:
            i0, i1 = i1, i0
        segment = self._candles[i0:i1 + 1]
        if not segment:
            return None
        max_h = max(segment, key=lambda cc: cc.high).high
        for j in range(i1, i0 - 1, -1):
            if self._candles[j].high == max_h:
                return j
        return None


# ---------------------------
# High-level Detector Wrapper
# ---------------------------

class PatternDetector:
    """
    Convenience wrapper:
    - Provide candles, meta (symbol, tf).
    - Optionally seed FIX area from UI (then call accept_fix()).
    - Call feed() in a loop; read result after each step or when DONE.
    """

    def __init__(self, symbol: str, tf_minutes: int, cfg: Optional["PatternConfig"] = None):
        meta = PatternMeta(symbol=symbol, tf_minutes=tf_minutes, direction="short")
        self.fsm = PatternStateMachine(meta=meta, cfg=cfg)

    def seed_fix(self, left_ts: int, right_ts: int, top: float, bottom: float, accept: bool = True):
        self.fsm.set_fix(left_ts, right_ts, top, bottom, accept)
        if accept:
            self.fsm.accept_fix()

    def run(self, candles: List[Candle]) -> PatternResult:
        for c in candles:
            self.fsm.feed(c)
        return self.fsm.result


# ---------------------------
# Simple module self-test (optional)
# ---------------------------

if __name__ == "__main__":
    # Minimal smoke test with fake data to ensure no syntax/runtime import errors.
    import random, time

    def mk(ts, o, h, l, c):
        return Candle(ts, o, h, l, c, volume=1.0, ts_close_ms=ts)

    now = int(time.time() * 1000)
    cs = []
    price = 100.0
    for i in range(300):
        o = price + random.uniform(-1, 1)
        h = o + random.uniform(0, 3)
        l = o - random.uniform(0, 3)
        c = l + (h - l) * random.random()
        price = c
        ts = now + i * 60_000
        cs.append(mk(ts, o, h, l, c))

    det = PatternDetector("TESTUSDT", 15)
    # Seed some FIX area roughly in first third of series
    det.seed_fix(left_ts=cs[20].ts_close_ms, right_ts=cs[35].ts_close_ms, top=max(x.high for x in cs[20:35]), bottom=min(x.low for x in cs[20:35]), accept=True)
    res = det.run(cs)
    print("[selftest] stage:", res.stage.name)
    print("[selftest] json length:", len(res.to_json()))

    # demo snap helpers
    if res.ray is None:
        det.fsm.snap_ray_to_low(cs[40].ts_close_ms)
    if res.hi_pattern is None and det.fsm._post_fix_low_idx is not None:
        # simulate a few more bars to get HI
        for k in range(20):
            det.fsm.feed(cs[min(len(cs)-1, 60+k)])
    print("[selftest] ray:", det.fsm.result.ray)

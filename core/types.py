from dataclasses import dataclass
from typing import List, Optional, Literal, Dict, Any

@dataclass
class Candle:
    ts: int   # ms
    o: float; h: float; l: float; c: float; v: float = 0.0

@dataclass
class Series:
    symbol: str
    tf_minutes: int
    candles: List[Candle]

StateName = Literal["FIX_WAIT","RAY_WAIT","RAY_TOUCHED","HI_LOCKED","PREFIX_WAIT","BA25_WAIT","DONE"]

@dataclass
class PatternMeta:
    symbol: str
    tf: str
    dt: str

@dataclass
class PatternState:
    name: StateName
    meta: PatternMeta
    fix_box: Optional[Dict[str, Any]] = None    # {x0,x1, y_top,y_bot, ts_left, ts_right, …}
    ray: Optional[Dict[str, Any]] = None         # {lo_index, y, ts0, ts_touch, …}
    hi_zone: Optional[Dict[str, Any]] = None     # {i0,i1, h_max}
    prefix_box: Optional[Dict[str, Any]] = None  # {x0,x1, …}
    ba25: Optional[Dict[str, Any]] = None        # {lo_index, ts0, ts_touch, …}
    notes: Dict[str, Any] = None
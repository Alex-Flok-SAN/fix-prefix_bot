#!/usr/bin/env python3
import json, sys

def make(
    symbol, tf, side,
    p, f, zl, zh, l1, l2, l3, sl, tp1, tp2, tp3,
    dyn_w=None, dyn_d=None, poc_d_in=None, vah_d=None, val_d=None, poc_m=None
):
    return {
      "symbol": symbol.upper(),
      "tf": tf,
      "type": f"FPF_{'LONG' if side=='long' else 'SHORT'}",
      "window_utc": [None, None],
      "tick_size": 0.0001,
      "P": {"t": None, "price": float(p)},
      "F": {"t": None, "price": float(f)},
      "I": {"t": None, "dir": "up" if side=='long' else "down"},
      "context_levels": {
        "dyn_weekly": dyn_w, "dyn_daily": dyn_d,
        "poc_daily_inside_prefix": poc_d_in,
        "vah_daily": vah_d, "val_daily": val_d, "poc_monthly": poc_m
      },
      "return_zone": {"low": float(zl), "high": float(zh), "source": "prefix/retest"},
      "entry_ladder": [
        {"tag":"L1","price":float(l1),"portion":0.15,"wind_ticks":5},
        {"tag":"L2","price":float(l2),"portion":0.35,"wind_ticks":10},
        {"tag":"L3","price":float(l3),"portion":0.50,"wind_ticks":15}
      ],
      "stop": {"rule":"cluster-in-prefix","price":float(sl),"offset_ticks":2},
      "tps": [
        {"tag":"TP1","price":float(tp1),"portion":0.25,"action":"to_breakeven"},
        {"tag":"TP2","price":float(tp2),"portion":0.35},
        {"tag":"TP3","price":float(tp3),"portion":0.40}
      ],
      "rr_policy": {"half_pos_min_2R": True, "full_pos_min_3R": True},
      "news_window": False,
      "no_reentry": True
    }

if __name__ == "__main__":
    if len(sys.argv) < 15:
        print("usage: make_fpf_label.py SYMBOL TF SIDE P F ZL ZH L1 L2 L3 SL TP1 TP2 TP3", file=sys.stderr)
        sys.exit(1)
    args = sys.argv[1:]
    sym, tf, side = args[0], args[1], args[2]
    nums = list(map(float, args[3:15]))
    payload = make(sym, tf, side, *nums)
    print(json.dumps(payload, ensure_ascii=False))
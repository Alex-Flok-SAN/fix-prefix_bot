# core/volume_profile_engine.py

import json
import hashlib
from typing import Dict
from typing import List

class VolumeProfileEngine:
    def __init__(self, bus, p):
        self.bus = bus
        self.p = p
        self._last_pub_ts = {}
        # delta-dedup: remember last published payload hash per key
        self._last_payload_hash: Dict[Tuple[str, str], str] = {}
        # monotonically increasing sequence per key for consumers
        self._seq: Dict[Tuple[str, str], int] = defaultdict(int)

    def _format_and_dedupe(self, levels: List[dict]) -> List[dict]:
        """Normalize payload: keep one level per type (prefer higher heat), quantize price, stable sort by priority."""
        prio = {t:i for i,t in enumerate(["VWAP_D","VWAP_S","POC_D","POC_S","VAH_D","VAL_D","VAH_S","VAL_S","HOD","LOD","SWING_H","SWING_L","ROUND"])}
        best: Dict[str, dict] = {}
        for lv in levels:
            lt = str(lv.get("type",""))
            price = float(lv.get("price", 0.0))
            meta = lv.get("meta") or {}
            # quantize price to 0.5 (BTC) to reduce noise; adjust if you use tick size
            qprice = round(price / 0.5) * 0.5
            heat = float(meta.get("heat", 0.0) or 0.0)
            cand = {"type": lt, "price": qprice}
            if meta:
                cand["meta"] = meta
            prev = best.get(lt)
            if prev is None or float((prev.get("meta") or {}).get("heat", 0.0)) < heat:
                best[lt] = cand
        # stable sort by priority then by price
        out = list(best.values())
        out.sort(key=lambda x: (prio.get(x.get("type",""), 999), x.get("price", 0.0)))
        # limit payload size
        return out[:16]

    def _maybe_publish(self, key, force=False):
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

        # Normalize/dedupe/sort and delta-dedup via hash
        norm_levels = self._format_and_dedupe(raw_levels)
        symbol, tf = key
        payload_obj = {"version": 1, "symbol": symbol, "tf": tf, "levels": norm_levels}
        blob = json.dumps(payload_obj, sort_keys=True, separators=(",", ":"))
        h = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        if not force and self._last_payload_hash.get(key) == h:
            return
        self._last_payload_hash[key] = h
        self._last_pub_ts[key] = now
        self._seq[key] += 1
        payload_obj["seq"] = self._seq[key]

        # Debug one-liner (can be commented out later)
        # print(f"[VPE] publish seq={payload_obj['seq']} {key} n={len(norm_levels)} sample={norm_levels[:2]}")

        self.bus.publish("levels.update", payload_obj)

    def flush(self, symbol: str, tf: str) -> None:
        key = (symbol, tf)
        self._maybe_publish(key, force=True)


# scripts/demo_levels_publisher.py
# Ensure core/ is importable when running from scripts/
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import argparse
import csv
import time
from typing import Dict

from core.event_bus import EventBus
from core.volume_profile_engine import VolumeProfileEngine, ProfileParams


def main() -> None:
    ap = argparse.ArgumentParser(description="Feed VolumeProfileEngine from CSV and print levels.update events")
    ap.add_argument("--csv", required=True, help="Path to M1 CSV (with ts_open_ms, open, high, low, close, volume ...)")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--tf", default="1m")
    ap.add_argument("--speed", type=float, default=0.0, help="Delay between bars in seconds; 0 = as fast as possible")
    ap.add_argument("--throttle", type=float, default=0.5, help="Publish throttle seconds in VolumeProfileEngine")
    ap.add_argument("--quiet", action="store_true", help="Do not print levels.update payloads; only progress logs")
    args = ap.parse_args()

    if not os.path.exists(args.csv):
        print(f"[ERR] CSV not found: {args.csv}")
        return

    print(f"[run] demo_levels_publisher: csv={args.csv} symbol={args.symbol} tf={args.tf} speed={args.speed}s throttle={args.throttle}s")

    # Init EventBus and VPE
    bus = EventBus()
    params = ProfileParams()
    params.publish_throttle_s = args.throttle
    vpe = VolumeProfileEngine(bus, params)
    print("[run] VolumeProfileEngine ready, flush:", hasattr(vpe, "flush"))

    # Subscriber to see outgoing level publications
    def on_levels(msg: Dict):
        if args.quiet:
            return
        levels = msg.get("levels", [])
        print("[levels.update]", msg.get("symbol"), msg.get("tf"), "seq=", msg.get("seq"), "->", len(levels), "lvl(s)")
        if levels:
            print("  sample:", levels[:2])

    bus.subscribe("levels.update", on_levels)

    # Stream minutes from CSV
    sent = 0
    with open(args.csv, "r", newline="") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            try:
                candle = {
                    "symbol": args.symbol,
                    "tf": args.tf,
                    "open_time": int(row["ts_open_ms"]),
                    "close_time": int(row["ts_open_ms"]) + 60_000,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                    "taker_buy_base": float(row.get("taker_buy_base", 0.0) or 0.0),
                }
            except Exception as e:
                print(f"[WARN] bad row #{sent+1}: {e}")
                continue

            vpe.on_minute(candle)
            sent += 1
            if sent % 10000 == 0:
                print(f"  [feed] sent {sent} bars…")
            if args.speed > 0:
                time.sleep(args.speed)

    # Force publish at end (ignore throttle)
    if hasattr(vpe, "flush"):
        vpe.flush(args.symbol, args.tf)
        print("[flush] forced publish")

    print(f"[done] fed {sent} bars from {args.csv}")


if __name__ == "__main__":
    main()
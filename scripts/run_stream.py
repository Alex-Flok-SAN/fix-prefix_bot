# scripts/run_stream.py
# Glue runner: streams candles (CSV/offline), builds levels via VolumeProfileEngine,
# runs FixPrefixDetector, and tracks outcomes via OutcomeTracker.
# Usage examples:
#   python scripts/run_stream.py \
#     --mode csv --symbol ETHUSDT --tf 1m \
#     --dir data/history/ETHUSDT \
#     --speed 0.0 --throttle 0.5 \
#     --out-signals data/out/ETH_signals.csv \
#     --out-outcomes data/out/ETH_outcomes.csv

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import argparse
import csv
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json

from core.event_bus import EventBus
from core.volume_profile_engine import VolumeProfileEngine, ProfileParams
from core.fix_prefix_detector import FixPrefixDetector
from core.outcome_tracker import OutcomeTracker


def iter_csv_rows(csv_paths: List[Path]):
    required = {"ts_open_ms", "open", "high", "low", "close", "volume"}
    for p in csv_paths:
        with p.open("r", newline="") as f:
            rdr = csv.DictReader(f)
            fields = set(rdr.fieldnames or [])
            if not required.issubset(fields):
                print(f"[SKIP] {p.name}: missing required columns {sorted(required - fields)}")
                continue
            for row in rdr:
                yield p.name, row


def main():
    ap = argparse.ArgumentParser(description="Run FPF bot pipeline (offline CSV stream or live)")
    ap.add_argument("--mode", choices=["csv", "live"], default="csv")
    ap.add_argument("--symbol", required=False, default="BTCUSDT")
    ap.add_argument("--tf", default="1m")

    # CSV/offline options
    ap.add_argument("--csv", nargs="*", help="One or more CSV files to stream (ts_open_ms, open, high, low, close, volume)")
    ap.add_argument("--dir", default=None, help="Directory with CSV files (glob * .csv)")
    ap.add_argument("--speed", type=float, default=0.0, help="Delay between bars in seconds; 0 = as fast as possible")
    ap.add_argument("--throttle", type=float, default=0.5, help="VolumeProfileEngine publish throttle (seconds)")
    ap.add_argument("--pattern", default="*_M1_*.csv", help="Glob pattern for CSV discovery when --dir is used (default: *_M1_*.csv)")

    # Detector params
    ap.add_argument("--vol-mult", type=float, default=2.0)
    ap.add_argument("--vol-sma-n", type=int, default=20)
    ap.add_argument("--min-bars-between", type=int, default=2)
    ap.add_argument("--zone-eps", type=float, default=0.0005)
    ap.add_argument("--eps-touch-pct", type=float, default=0.0005)
    ap.add_argument("--range-k-base", type=float, default=1.3)
    ap.add_argument("--vol-round-mult", type=float, default=1.3)

    ap.add_argument("--require-conf-round", dest="require_conf_round", action="store_true")
    ap.add_argument("--no-require-conf-round", dest="require_conf_round", action="store_false")
    ap.set_defaults(require_conf_round=True)

    ap.add_argument("--range-k-round-bonus", type=float, default=0.2)

    ap.add_argument("--disable-swing-without-conf", dest="disable_swing_without_conf", action="store_true")
    ap.add_argument("--allow-swing-without-conf", dest="disable_swing_without_conf", action="store_false")
    ap.set_defaults(disable_swing_without_conf=True)

    ap.add_argument("--min-stop-ticks", type=int, default=2)
    ap.add_argument("--stop-offset-ticks", type=int, default=3, help="Offset for SL beyond key high/low in ticks")
    ap.add_argument("--active-hours", default="6-20", help="UTC hours window 'start-end' or 'all' to disable")

    ap.add_argument("--entry-mode", choices=["break", "retest1"], default="break", help="Signal entry logic: immediate break or 1-bar retest into zone")

    # New dynamic stop logic arguments
    ap.add_argument("--min-stop-alpha", type=float, default=0.0, help="ATR multiplier for dynamic minimum stop size")
    ap.add_argument("--tick-size-map", type=str, default=None, help="JSON mapping symbol->tick_size for stop calculations")
    ap.add_argument("--lock-level-on-fix", action="store_true", default=False, help="Prevent changing the level after fix")
    ap.add_argument("--allow-level-upgrade", action="store_true", default=True, help="Allow upgrading level to more significant type after fix")

    # Outputs
    ap.add_argument("--out-signals", default=None, help="Path to save signal.detected events as CSV")
    ap.add_argument("--out-outcomes", default=None, help="Path to save signal.outcome events as CSV")
    ap.add_argument("--quiet", action="store_true", help="Reduce console output")

    ap.add_argument(
        "--retest-for-long",
        action="store_true",
        help="Enable conditional retest mode for LONG signals (switch break->retest1 when conditions are met)."
    )
    ap.add_argument(
        "--retest-for-short",
        action="store_true",
        help="Enable conditional retest mode for SHORT signals (switch break->retest1 when conditions are met)."
    )
    ap.add_argument(
        "--retest-only-for-levels",
        nargs="+",
        default=None,
        help="Restrict conditional retest to these level types (e.g. POC_D POC_S VWAP_D VWAP_S VAH_D VAL_D). If omitted, any level type may trigger retest."
    )
    ap.add_argument(
        "--retest-min-conf",
        type=int,
        default=2,
        help="Minimum confluence count (conf_n) required to enable conditional retest (default: 2)."
    )
    args = ap.parse_args()

    active_hours: Optional[Tuple[int,int]]
    if isinstance(args.active_hours, str) and args.active_hours.lower() == "all":
        active_hours = None
    else:
        try:
            h1, h2 = str(args.active_hours).split("-", 1)
            active_hours = (int(h1), int(h2))
        except Exception:
            active_hours = (6, 20)

    # Parse tick_size_map JSON if provided
    tick_size_map = None
    if args.tick_size_map:
        try:
            tick_size_map = json.loads(args.tick_size_map)
        except Exception as e:
            print(f"[ERR] Failed to parse --tick-size-map JSON: {e}")
            return

    # Prepare sources
    csv_paths: List[Path] = []
    if args.mode == "csv":
        if args.csv:
            csv_paths.extend([Path(p) for p in args.csv])
        if args.dir:
            for p in sorted(Path(args.dir).glob(args.pattern)):
                name = p.name.lower()
                if "signals" in name or "outcomes" in name:
                    continue
                csv_paths.append(p)
        if not csv_paths:
            print("[ERR] No CSV files provided. Use --csv or --dir.")
            return
        for p in csv_paths:
            if not p.exists():
                print(f"[ERR] CSV not found: {p}")
                return

    # Init bus and components
    bus = EventBus()
    params = ProfileParams()
    params.publish_throttle_s = args.throttle
    vpe = VolumeProfileEngine(bus, params)
    detector = FixPrefixDetector(
        bus,
        vol_mult=args.vol_mult,
        vol_sma_n=args.vol_sma_n,
        min_bars_between=args.min_bars_between,
        zone_eps=args.zone_eps,
        eps_touch_pct=args.eps_touch_pct,
        range_k_base=args.range_k_base,
        vol_round_mult=args.vol_round_mult,
        require_conf_for_round=args.require_conf_round,
        range_k_round_bonus=args.range_k_round_bonus,
        disable_swing_without_conf=args.disable_swing_without_conf,
        min_stop_ticks=args.min_stop_ticks,
        stop_offset_ticks=args.stop_offset_ticks,
        active_hours=active_hours,
        entry_mode=args.entry_mode,
        min_stop_alpha=args.min_stop_alpha,
        tick_size_map=tick_size_map,
        lock_level_on_fix=args.lock_level_on_fix,
        allow_level_upgrade=args.allow_level_upgrade,
        retest_only_for_levels=args.retest_only_for_levels,
        retest_min_conf=args.retest_min_conf,
        retest_for_long=args.retest_for_long,
        retest_for_short=args.retest_for_short,
    )
    out_tracker = OutcomeTracker(bus, window_minutes=360)

    # Collectors
    signals: List[Dict] = []
    outcomes: List[Dict] = []

    def on_signal(msg: Dict):
        # Only final signals
        if msg.get("direction") in ("long", "short"):
            signals.append(msg)
            if not args.quiet:
                print(f"[signal] {msg.get('symbol')} {msg.get('tf')} {msg.get('direction')} L={msg.get('level_type')} ai={msg.get('ai_score')} ts={msg.get('ts_fix')}")

    def on_outcome(msg: Dict):
        outcomes.append(msg)
        if not args.quiet:
            print(f"[outcome] {msg.get('symbol')} {msg.get('tf')} {msg.get('status')} mfe={msg.get('mfe_R')} mae={msg.get('mae_R')} ts_fix={msg.get('ts_fix')}")

    bus.subscribe("signal.detected", on_signal)
    bus.subscribe("signal.outcome", on_outcome)

    if args.mode == "csv":
        print(
            f"[run] CSV stream: files={len(csv_paths)} pattern={args.pattern} symbol={args.symbol} tf={args.tf} "
            f"speed={args.speed}s throttle={args.throttle}s | det: k={args.range_k_base}+{args.range_k_round_bonus if args.require_conf_round else 0} "
            f"volR={args.vol_round_mult} stop>={args.min_stop_ticks}t off={args.stop_offset_ticks}t active={'all' if active_hours is None else f'{active_hours[0]}-{active_hours[1]}'} entry={args.entry_mode}"
        )
        sent = 0
        for fname, row in iter_csv_rows(csv_paths):
            # Build candle
            try:
                ot = int(row["ts_open_ms"])  # open time (ms)
                ct = ot + 60_000
                candle = {
                    "symbol": args.symbol,
                    "tf": args.tf,
                    "open_time": ot,
                    "close_time": ct,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                }
            except Exception as e:
                print(f"[WARN] skip bad row in {fname}: {e}")
                continue

            # Feed engines
            vpe.on_minute(candle)
            detector.on_candle(candle)
            bus.publish("market.candle", candle)  # for OutcomeTracker (and any other consumers)

            sent += 1
            if not args.quiet and sent % 10000 == 0:
                print(f"  [feed] sent {sent} bars… last={ct}")
            if args.speed > 0:
                time.sleep(args.speed)

        # Force last publish of levels
        if hasattr(vpe, "flush"):
            vpe.flush(args.symbol, args.tf)

        print(f"[done] fed {sent} bars")
        # Diagnostics summary (if enabled in detector)
        if hasattr(detector, "dump_stats"):
            detector.dump_stats()

    else:
        print("[run] LIVE mode is a placeholder here. Hook your exchange stream and publish market.candle events.")
        print("      Components are running: VolumeProfileEngine, FixPrefixDetector, OutcomeTracker.")
        print("      Example to publish: bus.publish('market.candle', {...})")
        return

    # Save outputs if requested
    import pandas as pd
    if args.out_signals:
        Path(args.out_signals).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(signals).to_csv(args.out_signals, index=False)
        if not args.quiet:
            print(f"[save] signals -> {args.out_signals} ({len(signals)})")
    if args.out_outcomes:
        Path(args.out_outcomes).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(outcomes).to_csv(args.out_outcomes, index=False)
        if not args.quiet:
            print(f"[save] outcomes -> {args.out_outcomes} ({len(outcomes)})")


if __name__ == "__main__":
    main()

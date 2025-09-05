#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

PAIRS = ["BNBUSDT", "ADAUSDT", "LTCUSDT", "AVAXUSDT", "XRPUSDT"]
TF = "1m"
DATA_DIR = "data_dl"
PATTERN = "{sym}_M1_2024-*.csv"   # можно поменять на нужный квартал/диапазон
OUT_DIR = "data/out"
QUIET = True

def run_cmd(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out_lines = []
    while True:
        line = p.stdout.readline()
        if not line:
            if p.poll() is not None:
                break
            continue
        out_lines.append(line.rstrip())
        print(line.rstrip())
    return p.returncode, out_lines

def parse_stats(lines):
    stats = {
        "candidate": 0,
        "ok_long": 0,
        "ok_short": 0,
        "impulse_fail": 0,
        "stop_too_small": 0,
        "no_levels": 0,
        "conversion_ok": ""
    }
    in_block = False
    for ln in lines:
        if ln.strip().startswith("[detector.stats]"):
            in_block = True
            continue
        if in_block:
            if not ln.strip():
                in_block = False
                continue
            parts = ln.strip().split()
            if not parts:
                continue
            key = parts[0]
            if key in stats and key != "conversion_ok":
                try:
                    stats[key] = int(parts[-1])
                except Exception:
                    pass
            if key == "conversion_ok":
                stats["conversion_ok"] = " ".join(parts[2:])
    return stats

def main():
    Path(OUT_DIR).mkdir(parents=True, exist_ok=True)
    rows = []
    for sym in PAIRS:
        pattern = PATTERN.format(sym=sym)
        print(f"=== {sym} ===")
        cmd = [
            sys.executable, "scripts/run_stream.py",
            "--mode", "csv",
            "--symbol", sym,
            "--tf", TF,
            "--dir", DATA_DIR,
            "--pattern", pattern,
            "--speed", "0",
            "--throttle", "0",
            "--out-signals", f"{OUT_DIR}/{sym}_signals"
        ]
        if QUIET:
            cmd.append("--quiet")
        code, lines = run_cmd(cmd)
        stats = parse_stats(lines)
        rows.append((
            sym,
            stats.get("candidate", 0),
            stats.get("ok_long", 0),
            stats.get("ok_short", 0),
            stats.get("impulse_fail", 0),
            stats.get("stop_too_small", 0),
            stats.get("no_levels", 0),
            stats.get("conversion_ok", "")
        ))
    # Печать сводки
    print("\nPAIR\tCANDIDATE\tOK_LONG\tOK_SHORT\tIMP_FAIL\tSTOP_SMALL\tNO_LEVELS\tCONV")
    for r in rows:
        print(f"{r[0]}\t{r[1]}\t{r[2]}\t{r[3]}\t{r[4]}\t{r[5]}\t{r[6]}\t{r[7]}")

if __name__ == "__main__":
    main()
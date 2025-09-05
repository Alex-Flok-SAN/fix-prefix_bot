#!/usr/bin/env python3
"""
parquet_to_csv.py

Convert all per-month parquet files matching pattern into CSV with schema:
  ts_open_ms, open, high, low, close, volume, ts_close_ms

Usage:
  python parquet_to_csv.py --indir data_dl --pattern "*_M1_2024-*.parquet"

Requires: pandas, pyarrow (or fastparquet).
"""
import argparse
from pathlib import Path
import pandas as pd

def convert(indir: Path, pattern: str):
    files = sorted(indir.glob(pattern))
    if not files:
        print(f"No files matched: {indir}/{pattern}")
        return
    for fp in files:
        df = pd.read_parquet(fp)
        # Ensure schema
        cols = ["ts_open_ms","open","high","low","close","volume","ts_close_ms"]
        missing = [c for c in cols if c not in df.columns]
        if missing:
            raise ValueError(f"{fp.name}: missing columns {missing}")
        out = fp.with_suffix(".csv")
        df.to_csv(out, index=False)
        print(f"Converted: {fp.name} -> {out.name} ({len(df)} rows)")
    print("Done.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", default="data_dl", help="Directory with parquet files")
    ap.add_argument("--pattern", default="*.parquet", help="Glob pattern, e.g. '*_M1_2024-*.parquet'")
    args = ap.parse_args()
    convert(Path(args.indir), args.pattern)

if __name__ == "__main__":
    main()

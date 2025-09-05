import sys, os, pandas as pd

out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
files = [
    os.path.join(out_dir, "BTCUSDT_M1_2024-01.parquet"),
    os.path.join(out_dir, "BTCUSDT_M1_2024-02.parquet"),
    os.path.join(out_dir, "BTCUSDT_M1_2024-03.parquet"),
]

for f in files:
    if not os.path.exists(f):
        print(f"[skip] not found: {f}")
        continue
    df = pd.read_parquet(f)
    csv_path = f.replace(".parquet", ".csv")
    df.to_csv(csv_path, index=False)
    print(f"[ok] saved {csv_path} ({len(df)} rows)")

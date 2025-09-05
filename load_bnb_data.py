#!/usr/bin/env python3
"""
Load missing BNBUSDT minute data from 2025-08-16 to today
"""
from datetime import datetime, timedelta

# We have data up to: 2025-08-28 (last file)
# Need data from: 2025-08-29 to today (2025-09-02)

start_date = "2025-08-29"
end_date = datetime.now().strftime("%Y-%m-%d")

print(f"Loading BNBUSDT M1 data from {start_date} to {end_date}")
print("This will fill the gap: ~4 days of minute data")
print("Estimated download time: 1-2 minutes\n")

# Run the fetch command
import subprocess
import sys

cmd = [
    sys.executable,
    "utils/fetch_binance_klines.py",
    "--symbols", "BNBUSDT",
    "--start", start_date,
    "--end", end_date,
    "--tf", "1m",
    "--market", "futures",
    "--outdir", "data_1m"
]

print("Running command:")
print(" ".join(cmd))
print("\n" + "="*50 + "\n")

result = subprocess.run(cmd, capture_output=True, text=True)

# Print output
if result.stdout:
    print(result.stdout)
if result.stderr:
    print("Errors:", result.stderr)

if result.returncode == 0:
    print("\n✅ Data loaded successfully!")
    print(f"Check data_1m/ folder for new files")
else:
    print(f"\n❌ Failed with code: {result.returncode}")
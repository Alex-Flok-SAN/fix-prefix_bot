#!/usr/bin/env python3
"""
Load 3 months of ENAUSDT minute data
"""
from datetime import datetime, timedelta

# Load last 3 months of data
end_date = datetime.now()
start_date = end_date - timedelta(days=90)  # ~3 months

start_str = start_date.strftime("%Y-%m-%d")
end_str = end_date.strftime("%Y-%m-%d")

print(f"Loading ENAUSDT M1 data from {start_str} to {end_str}")
print("This will load: ~3 months of minute data")
print("Estimated download time: 2-3 minutes\n")

# Run the fetch command
import subprocess
import sys

cmd = [
    sys.executable,
    "utils/fetch_binance_klines.py",
    "--symbols", "ENAUSDT",
    "--start", start_str,
    "--end", end_str,
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
    print("\n✅ ENAUSDT data loaded successfully!")
    print(f"Check data_1m/ folder for new ENAUSDT files")
else:
    print(f"\n❌ Failed with code: {result.returncode}")
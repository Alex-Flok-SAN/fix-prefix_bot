#!/usr/bin/env python3
"""
Test FPF pattern detection on real data without GUI
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from datetime import datetime
import numpy as np

def find_fpf_pattern(df, window=100):
    """
    Simple FPF pattern detection:
    1. FIX - consolidation zone at extremum
    2. Impulse movement
    3. PREFIX - retest zone
    """
    patterns = []
    
    # Need at least window size of data
    if len(df) < window:
        return patterns
    
    for i in range(window, len(df) - window):
        # Look for potential FIX zone (low volatility)
        fix_start = i - window
        fix_end = i - window//2
        
        fix_data = df.iloc[fix_start:fix_end]
        fix_high = fix_data['high'].max()
        fix_low = fix_data['low'].min()
        fix_range = fix_high - fix_low
        
        # Calculate average range for comparison
        avg_range = (df['high'] - df['low']).rolling(20).mean().iloc[i]
        
        # FIX should have small range (consolidation)
        if fix_range < avg_range * 0.5:
            # Look for impulse after FIX
            impulse_data = df.iloc[fix_end:i]
            impulse_high = impulse_data['high'].max()
            impulse_low = impulse_data['low'].min()
            
            # Check for strong move (impulse)
            if impulse_high > fix_high + fix_range * 2:  # Bullish impulse
                # Look for PREFIX (retest)
                prefix_data = df.iloc[i:i+window//2]
                
                # Check if price returns near FIX zone
                if prefix_data['low'].min() < fix_high + fix_range:
                    patterns.append({
                        'type': 'FPF_LONG',
                        'fix_start_idx': fix_start,
                        'fix_end_idx': fix_end,
                        'fix_high': fix_high,
                        'fix_low': fix_low,
                        'impulse_high': impulse_high,
                        'prefix_idx': i,
                        'timestamp': df.iloc[i]['ts_open_ms'] if 'ts_open_ms' in df.columns else i
                    })
                    
            elif impulse_low < fix_low - fix_range * 2:  # Bearish impulse
                # Look for PREFIX (retest)
                prefix_data = df.iloc[i:i+window//2]
                
                # Check if price returns near FIX zone
                if prefix_data['high'].max() > fix_low - fix_range:
                    patterns.append({
                        'type': 'FPF_SHORT',
                        'fix_start_idx': fix_start,
                        'fix_end_idx': fix_end,
                        'fix_high': fix_high,
                        'fix_low': fix_low,
                        'impulse_low': impulse_low,
                        'prefix_idx': i,
                        'timestamp': df.iloc[i]['ts_open_ms'] if 'ts_open_ms' in df.columns else i
                    })
    
    return patterns

def main():
    print("FPF Pattern Detection Test")
    print("=" * 50)
    
    # Load test data
    data_file = Path("data_1m/BNBUSDT_M1_2024-10.csv")
    if not data_file.exists():
        print(f"❌ Data file not found: {data_file}")
        return
    
    print(f"Loading data from: {data_file.name}")
    df = pd.read_csv(data_file)
    print(f"Loaded {len(df)} rows")
    
    # Ensure we have the required columns
    required = ['open', 'high', 'low', 'close']
    if not all(col in df.columns for col in required):
        print(f"❌ Missing required columns. Available: {list(df.columns)}")
        return
    
    # Find patterns
    print("\nSearching for FPF patterns...")
    patterns = find_fpf_pattern(df, window=60)  # 1-hour window for M1 data
    
    if patterns:
        print(f"\n✅ Found {len(patterns)} FPF patterns!\n")
        
        for i, p in enumerate(patterns[:5], 1):  # Show first 5
            print(f"Pattern #{i}: {p['type']}")
            print(f"  FIX zone: index {p['fix_start_idx']}-{p['fix_end_idx']}")
            print(f"  FIX range: {p['fix_low']:.2f} - {p['fix_high']:.2f}")
            
            if p['type'] == 'FPF_LONG':
                print(f"  Impulse high: {p['impulse_high']:.2f}")
            else:
                print(f"  Impulse low: {p['impulse_low']:.2f}")
            
            print(f"  PREFIX at index: {p['prefix_idx']}")
            
            if 'ts_open_ms' in df.columns:
                ts = df.iloc[p['prefix_idx']]['ts_open_ms']
                dt = datetime.fromtimestamp(ts/1000)
                print(f"  Time: {dt.strftime('%Y-%m-%d %H:%M')}")
            print()
    else:
        print("❌ No FPF patterns found in the data")
        print("\nThis could mean:")
        print("  - The pattern detection needs tuning")
        print("  - The data doesn't contain clear FPF patterns")
        print("  - The window size needs adjustment")
    
    print("\n" + "=" * 50)
    print("To visualize patterns, run the GUI:")
    print("  python3 tools/tv_ingest_app.py")
    print("\nThen load this CSV file or drag a TradingView screenshot")

if __name__ == "__main__":
    main()
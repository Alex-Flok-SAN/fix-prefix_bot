#!/usr/bin/env python3
"""
Test script for tv_ingest_app functionality without GUI
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

print("Testing tv_ingest_app components...")
print("=" * 50)

# Test imports
try:
    from ai.ocr_engine import extract_ohlc_from_image
    print("✅ OCR engine imported successfully")
except Exception as e:
    print(f"❌ OCR engine import failed: {e}")

try:
    from core.ai_search_pattern.inference import detect_short_pattern
    print("✅ AI pattern detector imported")
except Exception as e:
    print(f"⚠️ AI pattern detector not available: {e}")

# Test data loading
import pandas as pd
data_dir = Path("data_1m")
csv_files = list(data_dir.glob("*.csv"))
print(f"\n📊 Found {len(csv_files)} CSV data files")

if csv_files:
    test_file = csv_files[0]
    print(f"Testing with: {test_file.name}")
    
    try:
        df = pd.read_csv(test_file)
        print(f"  - Loaded {len(df)} rows")
        print(f"  - Columns: {list(df.columns)[:5]}...")
        
        # Check if data has expected structure
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        has_all = all(col in df.columns or col.upper() in df.columns or col.title() in df.columns for col in required_cols)
        
        if has_all:
            print("✅ Data structure looks correct for FPF detection")
        else:
            print("⚠️ Data structure may need adjustment")
            print(f"  Available columns: {list(df.columns)}")
            
    except Exception as e:
        print(f"❌ Failed to load CSV: {e}")

# Test pattern detection logic
print("\n🔍 Testing FPF pattern detection...")
try:
    # Simple test to see if we can create detector components
    from core.fix_prefix_detector import FixPrefixDetector, Candle
    from core.event_bus import get_bus
    
    bus = get_bus()
    detector = FixPrefixDetector(bus)
    print("✅ FPF detector initialized")
    
    # Try to create a test candle
    test_candle = Candle(
        ts_open=1000000,
        ts_close=1001000,
        o=100.0, h=105.0, l=99.0, c=103.0, v=1000.0
    )
    print(f"✅ Test candle created: OHLC={test_candle.o}/{test_candle.h}/{test_candle.l}/{test_candle.c}")
    
except Exception as e:
    print(f"⚠️ FPF detector test failed: {e}")

print("\n" + "=" * 50)
print("tv_ingest_app component test complete!")
print("\nTo run the GUI application:")
print("  python3 tools/tv_ingest_app.py")
print("\nThe app will open a window where you can:")
print("  - Drag & drop TradingView screenshots")
print("  - Load CSV/Parquet data files")
print("  - Auto-detect FPF patterns")
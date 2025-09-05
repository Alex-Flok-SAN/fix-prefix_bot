#!/usr/bin/env python3
"""
Ручной тест FPF детектора с локальными данными
"""
import sys
import os
import pandas as pd
from datetime import datetime

sys.path.append('/Users/sashaflok/fpf_bot')

from core.ai_search_pattern.fpf_detector_new import FpfPatternDetector
from sync.simple_data_loader import load_data_for_analysis

def test_fpf_detector():
    """Тестирует FPF детектор на локальных данных"""
    
    # Создаем детектор с отладкой
    detector = FpfPatternDetector(debug=True)
    
    # Тестовая дата из графика
    test_date = datetime(2025, 7, 18, 8, 45)
    
    print("=" * 60)
    print("🧪 MANUAL FPF DETECTOR TEST")
    print("=" * 60)
    
    # Загружаем данные
    print(f"📊 Loading data for BNBUSDT 15m around {test_date}")
    data = load_data_for_analysis('BNBUSDT', '15m', test_date)
    
    if data is None or len(data) == 0:
        print("❌ No data loaded!")
        return
        
    print(f"✅ Loaded {len(data)} candles")
    print(f"📈 Price range: {data['low'].min():.2f} - {data['high'].max():.2f}")
    
    # Преобразуем в формат для детектора
    candles = []
    target_idx = None
    
    for i, row in data.iterrows():
        candle = (
            int(row['timestamp']),
            float(row['open']),
            float(row['high']),
            float(row['low']),
            float(row['close']),
            float(row.get('volume', 0))
        )
        candles.append(candle)
        
        # Находим ближайшую свечу к тестовой дате
        if target_idx is None:
            candle_time = pd.to_datetime(row['timestamp'], unit='ms')
            if abs((candle_time - test_date).total_seconds()) < 900:  # 15 минут
                target_idx = i
    
    print(f"🎯 Target candle index: {target_idx}")
    
    # Запускаем детектор
    print("\n" + "=" * 40)
    print("🔍 RUNNING FPF DETECTION")
    print("=" * 40)
    
    pattern = detector.detect_pattern(candles, target_idx)
    
    print("\n" + "=" * 40)
    print("📊 RESULTS")
    print("=" * 40)
    
    if pattern:
        print("🎉 FPF PATTERN FOUND!")
        print(f"🟢 FIX: {pattern.fix_start_idx}-{pattern.fix_end_idx} ({pattern.fix_low:.2f}-{pattern.fix_high:.2f})")
        print(f"🔻 LOY-FIX: idx={pattern.loy_fix_idx}, price={pattern.loy_fix_price:.2f}")
        print(f"🔺 HI-PATTERN: idx={pattern.hi_pattern_idx}, price={pattern.hi_pattern_price:.2f}")
        print(f"📏 RAY: {pattern.ray_price:.2f}, validated={pattern.ray_validated}")
        print(f"🎯 PREFIX: {pattern.prefix_end_price:.2f}-{pattern.prefix_start_price:.2f}")
        print(f"⭐ Confidence: {pattern.confidence:.1%}")
    else:
        print("❌ NO FPF PATTERN FOUND")
        
    return pattern

if __name__ == "__main__":
    test_fpf_detector()
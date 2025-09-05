#!/usr/bin/env python3
"""
Анализ и улучшение детекции FIX области
"""

import sys
import pandas as pd
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from core.ai_search_pattern.fpf_detector_new import FpfPatternDetector, CandleData

def load_and_analyze_fix():
    """Анализируем текущую детекцию FIX области"""
    
    # Загружаем данные
    data_file = Path("data_dl/BNBUSDT_M15_2025-05.csv")
    df = pd.read_csv(data_file)
    
    # Конвертируем в CandleData
    candlesticks = []
    for _, row in df.iterrows():
        candle = CandleData(
            timestamp=row['ts_open_ms'],
            open=row['open'],
            high=row['high'], 
            low=row['low'],
            close=row['close'],
            volume=row['volume']
        )
        candlesticks.append(candle)
    
    # OCR свеча (найденная ранее)
    ocr_idx = 462  # Соответствует скриншоту
    
    print("🔍 АНАЛИЗ FIX ОБЛАСТИ")
    print("=" * 50)
    
    # Детектор
    detector = FpfPatternDetector()
    pattern = detector.detect_pattern(candlesticks, ocr_candle_idx=ocr_idx)
    
    if pattern:
        print(f"\n✅ ТЕКУЩАЯ FIX ОБЛАСТЬ:")
        print(f"   Индексы: {pattern.fix_start_idx} - {pattern.fix_end_idx}")
        print(f"   Размер: {pattern.fix_end_idx - pattern.fix_start_idx + 1} свечей")
        print(f"   Цены: {pattern.fix_low:.2f} - {pattern.fix_high:.2f}")
        print(f"   Высота: {pattern.fix_high - pattern.fix_low:.2f}")
        
        # Анализ области вокруг OCR свечи
        print(f"\n📊 АНАЛИЗ ОБЛАСТИ ВОКРУГ OCR СВЕЧИ ({ocr_idx}):")
        
        for offset in range(-10, 11):
            idx = ocr_idx + offset
            if 0 <= idx < len(candlesticks):
                candle = candlesticks[idx]
                is_in_fix = pattern.fix_start_idx <= idx <= pattern.fix_end_idx
                marker = "🟦" if is_in_fix else "⬜"
                
                print(f"   {marker} {idx}: O={candle.open:.2f} H={candle.high:.2f} L={candle.low:.2f} C={candle.close:.2f}")
        
        # Рекомендации по улучшению
        print(f"\n💡 АНАЛИЗ КАЧЕСТВА FIX:")
        fix_candles = candlesticks[pattern.fix_start_idx:pattern.fix_end_idx+1]
        
        # Волатильность FIX области
        highs = [c.high for c in fix_candles]
        lows = [c.low for c in fix_candles]
        fix_volatility = (max(highs) - min(lows)) / min(lows) * 100
        
        print(f"   Волатильность FIX: {fix_volatility:.2f}%")
        print(f"   Качество: {'✅ Хорошо' if fix_volatility < 1.0 else '⚠️ Высокая волатильность'}")
        
        # Сравнение с соседними областями  
        print(f"\n📈 СРАВНЕНИЕ С СОСЕДЯМИ:")
        
        # Область слева от FIX
        left_start = max(0, pattern.fix_start_idx - 10)
        left_candles = candlesticks[left_start:pattern.fix_start_idx]
        if left_candles:
            left_highs = [c.high for c in left_candles]
            left_lows = [c.low for c in left_candles]
            left_vol = (max(left_highs) - min(left_lows)) / min(left_lows) * 100
            print(f"   Слева от FIX: волатильность {left_vol:.2f}%")
        
        # Область справа от FIX  
        right_end = min(len(candlesticks), pattern.fix_end_idx + 11)
        right_candles = candlesticks[pattern.fix_end_idx+1:right_end]
        if right_candles:
            right_highs = [c.high for c in right_candles]
            right_lows = [c.low for c in right_candles]
            right_vol = (max(right_highs) - min(right_lows)) / min(right_lows) * 100
            print(f"   Справа от FIX: волатильность {right_vol:.2f}%")
    else:
        print("❌ FIX область не найдена")

if __name__ == "__main__":
    load_and_analyze_fix()
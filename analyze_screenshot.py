#!/usr/bin/env python3
"""
Программный анализ FPF паттерна для скриншота
Sun 18-05-2025 12:00 BNBUSDT 15m

Данные из скриншота:
- Open: 647.21
- High: 648.55  
- Low: 647.10
- Close: 648.02
- Change: +0.81 (+0.13%)
"""

import sys
import pandas as pd
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from core.ai_search_pattern.fpf_detector_new import FpfPatternDetector, CandleData

def load_bnb_data():
    """Загружаем данные BNBUSDT"""
    data_file = Path("data_dl/BNBUSDT_M15_2025-05.csv")
    if not data_file.exists():
        print(f"❌ Файл {data_file} не найден")
        return None
        
    df = pd.read_csv(data_file)
    print(f"✅ Загружено {len(df)} свечей")
    
    # Конвертируем в формат CandleData
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
    
    return candlesticks

def find_ocr_candle(candlesticks):
    """Находим свечу максимально похожую на данные скриншота"""
    
    # Данные из скриншота
    screenshot_data = {
        'open': 647.21,
        'high': 648.55,
        'low': 647.10, 
        'close': 648.02
    }
    
    print(f"🎯 Ищем свечу похожую на скриншот: O={screenshot_data['open']}, H={screenshot_data['high']}, L={screenshot_data['low']}, C={screenshot_data['close']}")
    
    # Ищем свечу с минимальным отклонением
    best_idx = None
    best_score = float('inf')
    
    for i, candle in enumerate(candlesticks):
        # Вычисляем суммарное отклонение по всем OHLC
        score = (
            abs(candle.open - screenshot_data['open']) +
            abs(candle.high - screenshot_data['high']) +
            abs(candle.low - screenshot_data['low']) +
            abs(candle.close - screenshot_data['close'])
        )
        
        if score < best_score:
            best_score = score
            best_idx = i
            
    if best_idx is not None:
        candle = candlesticks[best_idx]
        from datetime import datetime
        import pytz
        actual_dt = datetime.fromtimestamp(candle.timestamp / 1000, tz=pytz.UTC)
        print(f"🎯 Наиболее похожая свеча: #{best_idx}")
        print(f"   Время: {actual_dt.strftime('%Y-%m-%d %H:%M')} UTC")
        print(f"   OHLC: O={candle.open}, H={candle.high}, L={candle.low}, C={candle.close}")
        print(f"   Отклонение: {best_score:.2f}")
        
        print(f"\n📊 Сравнение с скриншотом:")
        for field, expected in screenshot_data.items():
            actual = getattr(candle, field)
            diff = abs(actual - expected)
            status = "✅" if diff < 2.0 else "❌"
            print(f"   {field.upper()}: {actual:.2f} vs {expected:.2f} (Δ{diff:.2f}) {status}")
            
    return best_idx

def analyze_fpf_pattern(candlesticks, ocr_idx):
    """Анализируем FPF паттерн"""
    print(f"\n🔍 Анализ FPF паттерна...")
    
    detector = FpfPatternDetector()
    pattern = detector.detect_pattern(candlesticks, ocr_candle_idx=ocr_idx)
    
    if pattern:
        print(f"\n🎯 FPF PATTERN НАЙДЕН!")
        print(f"   Confidence: {pattern.confidence:.2f}")
        print(f"\n📦 FIX ОБЛАСТЬ:")
        print(f"   Индексы: {pattern.fix_start_idx} - {pattern.fix_end_idx}")
        print(f"   Цены: {pattern.fix_low:.2f} - {pattern.fix_high:.2f}")
        
        print(f"\n🔴 LOY-FIX:")
        print(f"   Индекс: {pattern.loy_fix_idx}")
        print(f"   Цена: {pattern.loy_fix_price:.2f}")
        
        print(f"\n🟢 HI-PATTERN:")
        print(f"   Индекс: {pattern.hi_pattern_idx}")
        print(f"   Цена: {pattern.hi_pattern_price:.2f}")
        
        print(f"\n⚡ RAY:")
        if hasattr(pattern, 'ray_validated') and pattern.ray_validated:
            print(f"   Валидирован: ✅")
            print(f"   Цена валидации: {pattern.ray_price:.2f}")
        else:
            print(f"   Валидирован: ❌")
            
        # Визуализация позиций
        print(f"\n📍 ПОЗИЦИИ НА ГРАФИКЕ:")
        total_candles = len(candlesticks)
        fix_pos = (pattern.fix_start_idx + pattern.fix_end_idx) / 2
        print(f"   FIX центр: {fix_pos:.0f} / {total_candles} ({fix_pos/total_candles*100:.1f}%)")
        print(f"   LOY-FIX: {pattern.loy_fix_idx} / {total_candles} ({pattern.loy_fix_idx/total_candles*100:.1f}%)")
        print(f"   HI-PATTERN: {pattern.hi_pattern_idx} / {total_candles} ({pattern.hi_pattern_idx/total_candles*100:.1f}%)")
        
    else:
        print("❌ FPF паттерн не найден")
        
    return pattern

def main():
    print("🚀 Программный анализ FPF паттерна")
    print("📸 Скриншот: Sun 18-05-2025 12:00 BNBUSDT 15m")
    
    # Загружаем данные
    candlesticks = load_bnb_data()
    if not candlesticks:
        return
        
    # Находим OCR свечу
    ocr_idx = find_ocr_candle(candlesticks)
    if ocr_idx is None:
        return
        
    # Анализируем паттерн
    pattern = analyze_fpf_pattern(candlesticks, ocr_idx)
    
    print(f"\n✅ Анализ завершен!")

if __name__ == "__main__":
    main()
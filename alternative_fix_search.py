#!/usr/bin/env python3
"""
Альтернативный поиск FIX области - пробуем разные позиции
"""

import sys
import pandas as pd
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from core.ai_search_pattern.fpf_detector_new import FpfPatternDetector, CandleData

def alternative_fix_search():
    """Альтернативный поиск FIX области"""
    
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
    
    print("🔍 АЛЬТЕРНАТИВНЫЙ ПОИСК FIX ОБЛАСТИ")
    print("=" * 50)
    
    # Основные точки из предыдущего анализа
    best_loy_fix = (435, 635.66)  # лучший LOY-FIX
    best_hi_pattern = (476, 652.18)  # HI-PATTERN
    
    print(f"📍 Известные точки:")
    print(f"   LOY-FIX: свеча #{best_loy_fix[0]}, цена {best_loy_fix[1]:.2f}")
    print(f"   HI-PATTERN: свеча #{best_hi_pattern[0]}, цена {best_hi_pattern[1]:.2f}")
    
    # Ищем FIX области в разных местах
    print(f"\n🎯 ВАРИАНТЫ FIX ОБЛАСТИ:")
    
    # Детектор для анализа плато
    detector = FpfPatternDetector()
    
    # Вариант 1: Ищем FIX между LOY-FIX и HI-PATTERN
    search_start = best_loy_fix[0] + 5  # немного после LOY-FIX
    search_end = best_hi_pattern[0] - 5   # немного до HI-PATTERN
    
    print(f"\n📊 ВАРИАНТ 1: FIX между LOY-FIX и HI-PATTERN ({search_start}-{search_end})")
    
    best_fixes = []
    
    # Анализируем разные окна в этой области
    for window_size in range(3, 10):
        for start_idx in range(search_start, search_end - window_size):
            end_idx = start_idx + window_size
            
            if end_idx >= len(candlesticks):
                continue
                
            # Рассчитываем параметры этого окна
            window_candles = candlesticks[start_idx:end_idx+1]
            
            if len(window_candles) < 3:
                continue
                
            # Высоты и минимумы
            highs = [c.high for c in window_candles]
            lows = [c.low for c in window_candles]
            
            fix_high = max(highs)
            fix_low = min(lows)
            fix_center = (fix_high + fix_low) / 2
            fix_height = fix_high - fix_low
            
            # Волатильность
            volatility = fix_height / fix_center
            
            # Проверяем базовые условия FIX
            # 1. LOY-FIX должен быть ниже этого FIX
            loy_below = best_loy_fix[1] < fix_low
            
            # 2. HI-PATTERN должен быть выше этого FIX  
            hi_above = best_hi_pattern[1] > fix_high
            
            # 3. Низкая волатильность (плато)
            low_volatility = volatility < 0.015  # 1.5%
            
            # 4. Последовательность: LOY-FIX < FIX < HI-PATTERN
            correct_sequence = (best_loy_fix[0] < start_idx < best_hi_pattern[0])
            
            if loy_below and hi_above and low_volatility and correct_sequence:
                score = 100 - (volatility * 1000) + (5 if end_idx - start_idx >= 5 else 0)
                best_fixes.append({
                    'start': start_idx,
                    'end': end_idx,
                    'low': fix_low,
                    'high': fix_high,
                    'center': fix_center,
                    'volatility': volatility * 100,
                    'score': score,
                    'size': end_idx - start_idx + 1
                })
    
    if best_fixes:
        # Сортируем по score
        best_fixes.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"\n✅ НАЙДЕНО {len(best_fixes)} валидных FIX областей:")
        
        for i, fix in enumerate(best_fixes[:5], 1):
            print(f"\n   {i}. СВЕЧИ {fix['start']}-{fix['end']} (размер {fix['size']}):")
            print(f"      Цены: {fix['low']:.2f} - {fix['high']:.2f}")
            print(f"      Волатильность: {fix['volatility']:.2f}%")
            print(f"      Score: {fix['score']:.1f}")
            
            # Проверим последовательность
            print(f"      Последовательность: LOY({best_loy_fix[0]}) → FIX({fix['start']}-{fix['end']}) → HI({best_hi_pattern[0]})")
            
            # Проверим расстояния
            loy_to_fix = fix['start'] - best_loy_fix[0]
            fix_to_hi = best_hi_pattern[0] - fix['end']
            
            print(f"      Расстояния: LOY→FIX={loy_to_fix} свечей, FIX→HI={fix_to_hi} свечей")
            
        # Выбираем лучший вариант
        best_fix = best_fixes[0]
        
        print(f"\n🏆 РЕКОМЕНДУЕМАЯ FIX ОБЛАСТЬ: {best_fix['start']}-{best_fix['end']}")
        print(f"   Цены: {best_fix['low']:.2f} - {best_fix['high']:.2f}")
        print(f"   Размер: {best_fix['size']} свечей")
        print(f"   Волатильность: {best_fix['volatility']:.2f}%")
        
        # Финальная проверка логики
        print(f"\n✅ ПРОВЕРКА БАЗЫ ЗНАНИЙ:")
        print(f"   1. LOY-FIX ({best_loy_fix[1]:.2f}) < FIX low ({best_fix['low']:.2f}): ✅")
        print(f"   2. FIX high ({best_fix['high']:.2f}) < HI-PATTERN ({best_hi_pattern[1]:.2f}): ✅") 
        print(f"   3. Последовательность LOY→FIX→HI: ✅")
        print(f"   4. Низкая волатильность FIX: ✅")
        
        # Расчет RAY и PREFIX
        ray_price = best_loy_fix[1]
        fix_height = best_fix['high'] - best_fix['low']
        prefix_target = ray_price - fix_height
        
        print(f"\n🎯 ТОРГОВЫЕ УРОВНИ:")
        print(f"   RAY (от LOY-FIX): {ray_price:.2f}")
        print(f"   FIX высота: {fix_height:.2f}")
        print(f"   PREFIX цель: {prefix_target:.2f}")
        
    else:
        print(f"\n❌ НЕ НАЙДЕНО валидных FIX областей в этом диапазоне")
        print(f"   Возможно, паттерн имеет другую структуру")
        
        # Попробуем поиск с менее строгими условиями
        print(f"\n🔄 ПОИСК С МЯГКИМИ УСЛОВИЯМИ...")
        
        relaxed_fixes = []
        for window_size in range(3, 8):
            for start_idx in range(search_start, search_end - window_size):
                end_idx = start_idx + window_size
                
                if end_idx >= len(candlesticks):
                    continue
                    
                window_candles = candlesticks[start_idx:end_idx+1]
                
                if len(window_candles) < 3:
                    continue
                    
                highs = [c.high for c in window_candles]
                lows = [c.low for c in window_candles]
                
                fix_high = max(highs)
                fix_low = min(lows)
                fix_center = (fix_high + fix_low) / 2
                fix_height = fix_high - fix_low
                volatility = fix_height / fix_center
                
                # Более мягкие условия
                loy_below = best_loy_fix[1] < fix_high  # лой ниже ВЕРХА фикса
                hi_above = best_hi_pattern[1] > fix_low   # хай выше НИЗА фикса
                moderate_volatility = volatility < 0.025  # 2.5%
                correct_sequence = (best_loy_fix[0] < start_idx < best_hi_pattern[0])
                
                if loy_below and hi_above and moderate_volatility and correct_sequence:
                    score = 50 - (volatility * 500)
                    relaxed_fixes.append({
                        'start': start_idx,
                        'end': end_idx,
                        'low': fix_low,
                        'high': fix_high,
                        'volatility': volatility * 100,
                        'score': score,
                        'size': end_idx - start_idx + 1
                    })
        
        if relaxed_fixes:
            relaxed_fixes.sort(key=lambda x: x['score'], reverse=True)
            print(f"\n⚠️ НАЙДЕНО {len(relaxed_fixes)} областей с мягкими условиями:")
            
            for i, fix in enumerate(relaxed_fixes[:3], 1):
                print(f"   {i}. СВЕЧИ {fix['start']}-{fix['end']}: {fix['low']:.2f}-{fix['high']:.2f}, волат {fix['volatility']:.2f}%")

if __name__ == "__main__":
    alternative_fix_search()
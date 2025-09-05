#!/usr/bin/env python3
"""
Расширенный анализ LOY-FIX - ищем в более широкой области
"""

import sys
import pandas as pd
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from core.ai_search_pattern.fpf_detector_new import FpfPatternDetector, CandleData

def extended_loy_analysis():
    """Расширенный поиск LOY-FIX в разных областях"""
    
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
    
    # OCR свеча
    ocr_idx = 462
    
    print("🔍 РАСШИРЕННЫЙ АНАЛИЗ LOY-FIX")
    print("=" * 50)
    
    # Детектор
    detector = FpfPatternDetector()
    pattern = detector.detect_pattern(candlesticks, ocr_candle_idx=ocr_idx)
    
    if not pattern:
        print("❌ Паттерн не найден")
        return
    
    print(f"✅ FIX область: {pattern.fix_start_idx}-{pattern.fix_end_idx}")
    print(f"   FIX цены: {pattern.fix_low:.2f} - {pattern.fix_high:.2f}")
    print(f"✅ HI-PATTERN: индекс {pattern.hi_pattern_idx}, цена {pattern.hi_pattern_price:.2f}")
    
    # 1. ПОИСК LOY-FIX В РАЗНЫХ ОБЛАСТЯХ
    print(f"\n🔍 ПОИСК LOY-FIX В РАЗНЫХ ОБЛАСТЯХ:")
    
    # А) Между FIX и HI-PATTERN
    print(f"\n📍 ОБЛАСТЬ A: МЕЖДУ FIX и HI-PATTERN ({pattern.fix_end_idx+1} - {pattern.hi_pattern_idx})")
    loy_candidates_a = []
    for i in range(pattern.fix_end_idx + 1, pattern.hi_pattern_idx):
        if i < len(candlesticks):
            candle = candlesticks[i]
            below_fix = candle.low < pattern.fix_low
            loy_candidates_a.append((i, candle.low, below_fix))
    
    if loy_candidates_a:
        loy_candidates_a.sort(key=lambda x: x[1])  # сортировка по цене
        print(f"   Топ-5 кандидатов:")
        for rank, (idx, low, below_fix) in enumerate(loy_candidates_a[:5], 1):
            marker = "✅" if below_fix else "❌"
            print(f"   {rank}. Свеча #{idx}: {low:.2f} {marker} (ниже FIX: {below_fix})")
    else:
        print(f"   Кандидатов не найдено")
    
    # Б) После HI-PATTERN 
    print(f"\n📍 ОБЛАСТЬ B: ПОСЛЕ HI-PATTERN ({pattern.hi_pattern_idx+1} - {pattern.hi_pattern_idx+30})")
    search_end_b = min(len(candlesticks), pattern.hi_pattern_idx + 30)
    loy_candidates_b = []
    for i in range(pattern.hi_pattern_idx + 1, search_end_b):
        candle = candlesticks[i]
        below_fix = candle.low < pattern.fix_low
        loy_candidates_b.append((i, candle.low, below_fix))
    
    if loy_candidates_b:
        loy_candidates_b.sort(key=lambda x: x[1])  # сортировка по цене
        print(f"   Топ-5 кандидатов:")
        for rank, (idx, low, below_fix) in enumerate(loy_candidates_b[:5], 1):
            marker = "✅" if below_fix else "❌"
            print(f"   {rank}. Свеча #{idx}: {low:.2f} {marker} (ниже FIX: {below_fix})")
    else:
        print(f"   Кандидатов не найдено")
    
    # В) Перед FIX областью
    print(f"\n📍 ОБЛАСТЬ C: ПЕРЕД FIX ({pattern.fix_start_idx-30} - {pattern.fix_start_idx-1})")
    search_start_c = max(0, pattern.fix_start_idx - 30)
    loy_candidates_c = []
    for i in range(search_start_c, pattern.fix_start_idx):
        candle = candlesticks[i]
        below_fix = candle.low < pattern.fix_low
        loy_candidates_c.append((i, candle.low, below_fix))
    
    if loy_candidates_c:
        loy_candidates_c.sort(key=lambda x: x[1])  # сортировка по цене
        print(f"   Топ-5 кандидатов:")
        for rank, (idx, low, below_fix) in enumerate(loy_candidates_c[:5], 1):
            marker = "✅" if below_fix else "❌"
            print(f"   {rank}. Свеча #{idx}: {low:.2f} {marker} (ниже FIX: {below_fix})")
    else:
        print(f"   Кандидатов не найдено")
    
    # 2. АНАЛИЗ ВСЕХ ВАЛИДНЫХ LOY-FIX
    print(f"\n✅ СВОДКА ВАЛИДНЫХ LOY-FIX (ниже FIX {pattern.fix_low:.2f}):")
    
    all_valid = []
    for area_name, candidates in [("A (FIX→HI)", loy_candidates_a), 
                                  ("B (после HI)", loy_candidates_b),
                                  ("C (перед FIX)", loy_candidates_c)]:
        valid_in_area = [(idx, low) for idx, low, below_fix in candidates if below_fix]
        if valid_in_area:
            best_idx, best_low = min(valid_in_area, key=lambda x: x[1])
            all_valid.append((area_name, best_idx, best_low))
            print(f"   {area_name}: свеча #{best_idx}, цена {best_low:.2f}")
        else:
            print(f"   {area_name}: НЕТ валидных")
    
    if all_valid:
        # Выбираем лучший LOY-FIX из всех областей
        best_area, best_idx, best_low = min(all_valid, key=lambda x: x[2])
        print(f"\n🏆 ЛУЧШИЙ LOY-FIX: область {best_area}, свеча #{best_idx}, цена {best_low:.2f}")
        
        # Проверим временную последовательность
        print(f"\n⏰ ВРЕМЕННАЯ ПОСЛЕДОВАТЕЛЬНОСТЬ:")
        print(f"   FIX: {pattern.fix_start_idx}-{pattern.fix_end_idx}")
        print(f"   LOY-FIX: {best_idx}")
        print(f"   HI-PATTERN: {pattern.hi_pattern_idx}")
        
        # Логика последовательности по базе
        if best_idx < pattern.fix_start_idx:
            print(f"   ❌ LOY-FIX ДО FIX - не соответствует базе")
        elif pattern.fix_start_idx <= best_idx <= pattern.fix_end_idx:
            print(f"   ❌ LOY-FIX ВНУТРИ FIX - не соответствует базе")
        elif pattern.fix_end_idx < best_idx < pattern.hi_pattern_idx:
            print(f"   ✅ LOY-FIX МЕЖДУ FIX и HI-PATTERN - соответствует базе")
        elif best_idx > pattern.hi_pattern_idx:
            print(f"   ❓ LOY-FIX ПОСЛЕ HI-PATTERN - возможно другой паттерн")
        
    else:
        print(f"\n❌ НЕТ ВАЛИДНЫХ LOY-FIX во всех областях")
        print(f"   Возможные причины:")
        print(f"   1. FIX область определена слишком широко")
        print(f"   2. Паттерн еще не сформирован")
        print(f"   3. Это другой тип разворотного паттерна")

if __name__ == "__main__":
    extended_loy_analysis()
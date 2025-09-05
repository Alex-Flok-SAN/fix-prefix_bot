#!/usr/bin/env python3
"""
Анализ и оптимизация позиций LOY-FIX и HI-PATTERN
"""

import sys
import pandas as pd
from pathlib import Path
from datetime import datetime

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from core.ai_search_pattern.fpf_detector_new import FpfPatternDetector, CandleData

def analyze_loy_hi_positioning():
    """Анализируем позиции LOY-FIX и HI-PATTERN"""
    
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
    
    print("🎯 АНАЛИЗ LOY-FIX И HI-PATTERN ПОЗИЦИЙ")
    print("=" * 50)
    
    # Детектор
    detector = FpfPatternDetector()
    pattern = detector.detect_pattern(candlesticks, ocr_candle_idx=ocr_idx)
    
    if not pattern:
        print("❌ Паттерн не найден")
        return
    
    # Анализ LOY-FIX
    print(f"\n🔴 LOY-FIX АНАЛИЗ:")
    print(f"   Индекс: {pattern.loy_fix_idx}")
    print(f"   Цена: {pattern.loy_fix_price:.2f}")
    
    # Проверим область поиска LOY-FIX 
    search_start = pattern.fix_end_idx + 1
    search_end = pattern.hi_pattern_idx
    
    print(f"   Область поиска: {search_start} - {search_end}")
    print(f"   Размер области: {search_end - search_start + 1} свечей")
    
    # Найдем все минимумы в этой области
    loy_candidates = []
    for i in range(search_start, search_end + 1):
        if i < len(candlesticks):
            candle = candlesticks[i]
            loy_candidates.append((i, candle.low, candle.high, candle.close))
    
    # Сортируем по минимуму
    loy_candidates.sort(key=lambda x: x[1])  # По low цене
    
    print(f"\n   📊 ТОП-5 КАНДИДАТОВ LOY-FIX:")
    for rank, (idx, low, high, close) in enumerate(loy_candidates[:5], 1):
        is_current = idx == pattern.loy_fix_idx
        marker = "👑" if is_current else f"{rank}"
        print(f"   {marker} Свеча #{idx}: Low={low:.2f}, High={high:.2f}, Close={close:.2f}")
    
    # Анализ HI-PATTERN
    print(f"\n🟢 HI-PATTERN АНАЛИЗ:")
    print(f"   Индекс: {pattern.hi_pattern_idx}")
    print(f"   Цена: {pattern.hi_pattern_price:.2f}")
    
    # Проверим область поиска HI-PATTERN (после FIX)
    hi_search_start = pattern.fix_end_idx + 1
    hi_search_end = len(candlesticks) - 1
    
    print(f"   Область поиска: {hi_search_start} - {hi_search_end}")
    print(f"   Размер области: {hi_search_end - hi_search_start + 1} свечей")
    
    # Найдем все максимумы
    hi_candidates = []
    for i in range(hi_search_start, min(hi_search_end + 1, len(candlesticks))):
        candle = candlesticks[i]
        hi_candidates.append((i, candle.high, candle.low, candle.close))
    
    # Сортируем по максимуму (убывание)
    hi_candidates.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\n   📊 ТОП-5 КАНДИДАТОВ HI-PATTERN:")
    for rank, (idx, high, low, close) in enumerate(hi_candidates[:5], 1):
        is_current = idx == pattern.hi_pattern_idx
        marker = "👑" if is_current else f"{rank}"
        print(f"   {marker} Свеча #{idx}: High={high:.2f}, Low={low:.2f}, Close={close:.2f}")
    
    # Проверка соответствия базе знаний
    print(f"\n📚 СООТВЕТСТВИЕ БАЗЕ ЗНАНИЙ:")
    
    # 1. LOY-FIX должен быть МЕЖДУ FIX и HI-PATTERN
    loy_between = pattern.fix_end_idx < pattern.loy_fix_idx < pattern.hi_pattern_idx
    print(f"   1. LOY-FIX между FIX и HI-PATTERN: {'✅' if loy_between else '❌'}")
    print(f"      FIX конец: {pattern.fix_end_idx}, LOY-FIX: {pattern.loy_fix_idx}, HI-PATTERN: {pattern.hi_pattern_idx}")
    
    # 2. LOY-FIX должен быть ниже области FIX
    loy_below_fix = pattern.loy_fix_price < pattern.fix_low
    print(f"   2. LOY-FIX ниже FIX области: {'✅' if loy_below_fix else '❌'}")
    print(f"      LOY-FIX: {pattern.loy_fix_price:.2f}, FIX low: {pattern.fix_low:.2f}")
    
    # 3. HI-PATTERN должен быть выше области FIX
    hi_above_fix = pattern.hi_pattern_price > pattern.fix_high
    print(f"   3. HI-PATTERN выше FIX области: {'✅' if hi_above_fix else '❌'}")
    print(f"      HI-PATTERN: {pattern.hi_pattern_price:.2f}, FIX high: {pattern.fix_high:.2f}")
    
    # 4. HI-PATTERN должен быть абсолютным максимумом после FIX
    is_absolute_max = True
    for i in range(pattern.fix_end_idx + 1, len(candlesticks)):
        if candlesticks[i].high > pattern.hi_pattern_price:
            is_absolute_max = False
            print(f"      ⚠️ Найден более высокий максимум на свече {i}: {candlesticks[i].high:.2f}")
            break
    
    print(f"   4. HI-PATTERN абсолютный максимум: {'✅' if is_absolute_max else '❌'}")
    
    # Рекомендации
    print(f"\n💡 РЕКОМЕНДАЦИИ:")
    all_checks = [loy_between, loy_below_fix, hi_above_fix, is_absolute_max]
    
    if all(all_checks):
        print("   ✅ Все проверки пройдены! Позиции оптимальны.")
    else:
        print("   ⚠️ Есть проблемы с позиционированием:")
        if not loy_between:
            print("     - LOY-FIX не между FIX и HI-PATTERN")
        if not loy_below_fix:
            print("     - LOY-FIX не ниже FIX области")
        if not hi_above_fix:
            print("     - HI-PATTERN не выше FIX области")
        if not is_absolute_max:
            print("     - HI-PATTERN не абсолютный максимум")
    
    # Временной анализ
    print(f"\n⏰ ВРЕМЕННОЙ АНАЛИЗ:")
    
    def format_time(candle_idx):
        if candle_idx < len(candlesticks):
            timestamp = candlesticks[candle_idx].timestamp
            dt = datetime.fromtimestamp(timestamp / 1000)
            return dt.strftime('%Y-%m-%d %H:%M')
        return "N/A"
    
    print(f"   FIX область: {format_time(pattern.fix_start_idx)} - {format_time(pattern.fix_end_idx)}")
    print(f"   LOY-FIX: {format_time(pattern.loy_fix_idx)}")
    print(f"   HI-PATTERN: {format_time(pattern.hi_pattern_idx)}")
    
    # Расчет интервалов
    fix_duration = (pattern.fix_end_idx - pattern.fix_start_idx + 1) * 15  # минут
    loy_to_hi_duration = (pattern.hi_pattern_idx - pattern.loy_fix_idx) * 15  # минут
    
    print(f"   FIX длительность: {fix_duration} минут")
    print(f"   LOY-FIX → HI-PATTERN: {loy_to_hi_duration} минут")

if __name__ == "__main__":
    analyze_loy_hi_positioning()
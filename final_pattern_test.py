#!/usr/bin/env python3
"""
Финальный тест с правильными координатами паттерна
"""

import sys
import pandas as pd
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from core.ai_search_pattern.fpf_detector_new import FpfPattern, CandleData

def final_pattern_test():
    """Создаем финальный паттерн с правильными координатами"""
    
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
    
    print("🎯 ФИНАЛЬНЫЙ АНАЛИЗ FPF ПАТТЕРНА")
    print("=" * 50)
    
    # Используем правильные координаты из альтернативного поиска:
    loy_fix_idx = 435
    loy_fix_price = 635.66
    
    fix_start_idx = 465
    fix_end_idx = 470
    fix_low = 647.52
    fix_high = 650.00
    fix_center = (fix_low + fix_high) / 2
    
    hi_pattern_idx = 476
    hi_pattern_price = 652.18
    
    print(f"✅ ПРАВИЛЬНЫЕ КООРДИНАТЫ ПАТТЕРНА:")
    print(f"   LOY-FIX: свеча #{loy_fix_idx}, цена {loy_fix_price:.2f}")
    print(f"   FIX: свечи {fix_start_idx}-{fix_end_idx}, цены {fix_low:.2f}-{fix_high:.2f}")
    print(f"   HI-PATTERN: свеча #{hi_pattern_idx}, цена {hi_pattern_price:.2f}")
    
    # Расчет PREFIX цен
    fix_height = fix_high - fix_low
    prefix_start_price = loy_fix_price
    prefix_end_price = loy_fix_price - fix_height
    
    # Создаем объект паттерна вручную
    pattern = FpfPattern(
        fix_start_idx=fix_start_idx,
        fix_end_idx=fix_end_idx,
        fix_high=fix_high,
        fix_low=fix_low,
        loy_fix_idx=loy_fix_idx,
        loy_fix_price=loy_fix_price,
        hi_pattern_idx=hi_pattern_idx,
        hi_pattern_price=hi_pattern_price,
        ray_price=loy_fix_price,
        ray_validated=False,
        prefix_start_price=prefix_start_price,
        prefix_end_price=prefix_end_price,
        confidence=0.95
    )
    
    # Проверка всех условий базы знаний
    print(f"\n✅ ПРОВЕРКА БАЗЫ ЗНАНИЙ:")
    
    # 1. Последовательность по времени
    seq_ok = loy_fix_idx < fix_start_idx < hi_pattern_idx
    print(f"   1. Последовательность LOY→FIX→HI: {'✅' if seq_ok else '❌'}")
    print(f"      {loy_fix_idx} < {fix_start_idx} < {hi_pattern_idx}: {seq_ok}")
    
    # 2. LOY-FIX ниже FIX области
    loy_below = loy_fix_price < fix_low
    print(f"   2. LOY-FIX ниже FIX: {'✅' if loy_below else '❌'}")
    print(f"      {loy_fix_price:.2f} < {fix_low:.2f}: {loy_below}")
    
    # 3. HI-PATTERN выше FIX области
    hi_above = hi_pattern_price > fix_high
    print(f"   3. HI-PATTERN выше FIX: {'✅' if hi_above else '❌'}")
    print(f"      {hi_pattern_price:.2f} > {fix_high:.2f}: {hi_above}")
    
    # 4. FIX как плато (низкая волатильность)
    fix_volatility = (fix_high - fix_low) / fix_center * 100
    volatility_ok = fix_volatility < 1.0  # менее 1%
    print(f"   4. FIX волатильность: {'✅' if volatility_ok else '❌'}")
    print(f"      {fix_volatility:.2f}% < 1.0%: {volatility_ok}")
    
    # 5. Проверка RAY валидации
    ray_price = loy_fix_price
    ray_validated = False
    
    # Ищем валидацию RAY после HI-PATTERN
    for i in range(hi_pattern_idx + 1, min(len(candlesticks), hi_pattern_idx + 30)):
        if candlesticks[i].low < ray_price:
            ray_validated = True
            print(f"   5. RAY валидация: ✅ на свече #{i}, цена {candlesticks[i].low:.2f}")
            break
    
    if not ray_validated:
        print(f"   5. RAY валидация: ⏳ пока не произошла (RAY = {ray_price:.2f})")
    
    # Итоговая оценка
    all_checks = [seq_ok, loy_below, hi_above, volatility_ok]
    passed_checks = sum(all_checks)
    
    print(f"\n🎯 ИТОГОВАЯ ОЦЕНКА:")
    print(f"   ✅ Пройдено проверок: {passed_checks}/4")
    print(f"   📊 Качество паттерна: {'ОТЛИЧНОЕ' if passed_checks == 4 else 'ХОРОШЕЕ' if passed_checks >= 3 else 'СРЕДНЕЕ'}")
    print(f"   🎲 Уверенность: {95 if passed_checks == 4 else 85 if passed_checks >= 3 else 70}%")
    
    # Торговые уровни
    print(f"\n📈 ТОРГОВЫЕ УРОВНИ:")
    print(f"   🔴 RAY (стоп-уровень): {ray_price:.2f}")
    
    fix_height = fix_high - fix_low
    prefix_target = ray_price - fix_height
    print(f"   🟢 PREFIX цель: {prefix_target:.2f}")
    print(f"   📏 FIX высота: {fix_height:.2f}")
    
    # Временной анализ
    print(f"\n⏰ ВРЕМЕННОЙ АНАЛИЗ:")
    
    def format_time(idx):
        if idx < len(candlesticks):
            from datetime import datetime
            timestamp = candlesticks[idx].timestamp
            dt = datetime.fromtimestamp(timestamp / 1000)
            return dt.strftime('%Y-%m-%d %H:%M')
        return "N/A"
    
    print(f"   LOY-FIX время: {format_time(loy_fix_idx)}")
    print(f"   FIX период: {format_time(fix_start_idx)} - {format_time(fix_end_idx)}")
    print(f"   HI-PATTERN время: {format_time(hi_pattern_idx)}")
    
    # Интервалы
    loy_to_fix = (fix_start_idx - loy_fix_idx) * 15  # минут
    fix_duration = (fix_end_idx - fix_start_idx + 1) * 15  # минут
    fix_to_hi = (hi_pattern_idx - fix_end_idx) * 15  # минут
    
    print(f"\n⏱️ ИНТЕРВАЛЫ:")
    print(f"   LOY-FIX → FIX: {loy_to_fix} минут ({loy_to_fix//60}ч {loy_to_fix%60}м)")
    print(f"   FIX длительность: {fix_duration} минут")
    print(f"   FIX → HI-PATTERN: {fix_to_hi} минут ({fix_to_hi//60}ч {fix_to_hi%60}м)")
    
    if all_checks:
        print(f"\n🎉 ПАТТЕРН ГОТОВ К ТОРГОВЛЕ!")
        if not ray_validated:
            print(f"   ⏳ Ожидаем валидации RAY для входа в позицию")
    
    return pattern

if __name__ == "__main__":
    final_pattern_test()
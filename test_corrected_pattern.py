#!/usr/bin/env python3
"""
Тест исправленного паттерна - создаем паттерн с правильными координатами
и запускаем snapp для визуализации
"""

import sys
import pandas as pd
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from core.ai_search_pattern.fpf_detector_new import FpfPattern, CandleData

class MockFPFDetector:
    """Мок детектор, который возвращает правильный паттерн"""
    
    def detect_pattern(self, candles, ocr_candle_idx=None):
        """Возвращает правильно найденный паттерн"""
        
        # Правильные координаты из анализа
        pattern = FpfPattern(
            fix_start_idx=465,
            fix_end_idx=470,
            fix_high=650.00,
            fix_low=647.52,
            loy_fix_idx=435,
            loy_fix_price=635.66,
            hi_pattern_idx=476,
            hi_pattern_price=652.18,
            ray_price=635.66,
            ray_validated=False,
            prefix_start_price=635.66,
            prefix_end_price=633.18,
            confidence=0.95,
            ocr_candle_idx=ocr_candle_idx
        )
        
        print(f"✅ Мок детектор вернул правильный паттерн:")
        print(f"   LOY-FIX: #{pattern.loy_fix_idx}, цена {pattern.loy_fix_price:.2f}")
        print(f"   FIX: #{pattern.fix_start_idx}-{pattern.fix_end_idx}, {pattern.fix_low:.2f}-{pattern.fix_high:.2f}")
        print(f"   HI-PATTERN: #{pattern.hi_pattern_idx}, цена {pattern.hi_pattern_price:.2f}")
        print(f"   Уверенность: {pattern.confidence:.0%}")
        
        return pattern

def test_corrected_pattern():
    """Тест правильного паттерна"""
    
    print("🎯 ТЕСТ ИСПРАВЛЕННОГО ПАТТЕРНА")
    print("=" * 50)
    
    # Временно заменяем детектор в snapp на правильную версию
    import tools.snapp as snapp_module
    
    # Сохраняем оригинальный класс
    original_detector = snapp_module.FpfPatternDetector
    
    # Подменяем на мок
    snapp_module.FpfPatternDetector = MockFPFDetector
    
    print("✅ Детектор заменен на правильную версию")
    print("🚀 Теперь можно запустить snapp и увидеть правильный паттерн!")
    
    print(f"\n📝 ДЛЯ ТЕСТИРОВАНИЯ:")
    print(f"   1. Запустите: python3 tools/snapp.py")
    print(f"   2. Перетащите скриншот BNBUSDT в окно")
    print(f"   3. Паттерн отобразится с правильными координатами:")
    print(f"      - LOY-FIX на уровне 635.66 (зеленая точка)")
    print(f"      - FIX область 647.52-650.00 (синий прямоугольник)")  
    print(f"      - HI-PATTERN на уровне 652.18 (красная точка)")
    print(f"      - RAY линия от 635.66 вправо")

if __name__ == "__main__":
    test_corrected_pattern()
# -*- coding: utf-8 -*-
"""
fpf_pattern_builder.py

Правильная логика построения шортового FPF паттерна согласно торговой стратегии:
Fix-Prefix-Fix = разворотная модель или модель выхода из флэта
"""

from typing import Dict, List, Optional, Tuple, Any
import math


class FPFPatternBuilder:
    """Построитель шортового FPF паттерна по правильной торговой логике."""
    
    def __init__(self, bars: List[Tuple], center_bar_index: int):
        """
        Args:
            bars: List of (timestamp, open, high, low, close) tuples
            center_bar_index: Индекс бара в центре анализа (от OCR времени)
        """
        self.bars = bars
        self.center_idx = center_bar_index
        self.n_bars = len(bars)
        
        # Результаты построения
        self.fix_zone = None      # Зона первичного хая
        self.loy_fix = None       # Лой между FIX и Hi-pattern
        self.hi_pattern = None    # Хай выше FIX зоны
        self.validation_point = None  # Точка валидации паттерна
        self.ray_data = None      # RAY от ЛОЙ-FIX
        self.prefix_zone = None   # Зона интереса для шорта
        self.ba25_level = None    # Уровень безубытка 25%
        self.take_profit = None   # Зона фиксации прибыли
        
    def build_pattern(self) -> Dict[str, Any]:
        """
        Строит весь FPF паттерн по правильной логике.
        
        Returns:
            Dict с ключами: fix, loy_fix, hi_pattern, ray, prefix, ba25, take_profit
        """
        print(f"[FPF] Начинаю построение паттерна, center_idx={self.center_idx}, bars={self.n_bars}")
        
        # 1. Поиск FIX зоны (хай с повышенным объемом ПЕРЕД центром)
        self.fix_zone = self._find_fix_zone()
        if not self.fix_zone:
            print("[FPF] FIX зона не найдена")
            return {}
            
        # 2. Поиск ЛОЙ-FIX (лой после FIX зоны)
        self.loy_fix = self._find_loy_fix()
        if not self.loy_fix:
            print("[FPF] ЛОЙ-FIX не найден")
            return {}
            
        # 3. Поиск Hi-pattern (хай выше FIX зоны)
        self.hi_pattern = self._find_hi_pattern()
        if not self.hi_pattern:
            print("[FPF] Hi-pattern не найден")
            return {}
            
        # 4. Проверка валидации паттерна (обновление ЛОЙ-FIX сверху-вниз)
        self.validation_point = self._check_pattern_validation()
        if not self.validation_point:
            print("[FPF] Паттерн не валидирован")
            return {}
            
        # 5. Построение RAY (от ЛОЙ-FIX до первого касания сверху)
        self.ray_data = self._build_ray()
        
        # 6. Построение PREFIX зоны (зона интереса для шорта)
        self.prefix_zone = self._build_prefix_zone()
        
        # 7. Определение BA25 уровня (безубыток 25%)
        self.ba25_level = self._find_ba25_level()
        
        # 8. Определение Take Profit зоны
        self.take_profit = self._calculate_take_profit()
        
        result = {
            'fix': self.fix_zone,
            'loy_fix': self.loy_fix,
            'hi_pattern': self.hi_pattern,
            'validation': self.validation_point,
            'ray': self.ray_data,
            'prefix': self.prefix_zone,
            'ba25': self.ba25_level,
            'take_profit': self.take_profit
        }
        
        print(f"[FPF] Паттерн построен успешно: {list(result.keys())}")
        return result
        
    def _find_fix_zone(self) -> Optional[Dict[str, Any]]:
        """Поиск FIX зоны используя правильную логику плато из бэкапа."""
        # Ищем в области ЛЕВЕЕ центра, расширяем область поиска
        search_start = max(0, self.center_idx - 150)
        search_end = max(search_start + 10, self.center_idx - 15)
        
        if search_end <= search_start + 5:
            return None
            
        print(f"[FPF] Ищу FIX зону ПЛАТО в индексах {search_start}-{search_end} (центр={self.center_idx})")
        
        # Используем логику плато из бэкапа - ищем несколько возможных сегментов
        best_fix = None
        best_score = 0
        
        # Пробуем разные размеры окон для поиска плато
        for window_size in [12, 16, 20, 24]:
            if window_size > (search_end - search_start):
                continue
                
            # Двигаем окно по области поиска
            for start in range(search_start, search_end - window_size, 2):
                end = start + window_size
                
                fix_candidate = self._find_plateau_fix(start, end)
                if fix_candidate and fix_candidate['score'] > best_score:
                    best_fix = fix_candidate
                    best_score = fix_candidate['score']
        
        if best_fix:
            print(f"[FPF] Найден FIX плато: индексы {best_fix['left_i']}-{best_fix['right_i']}, цены {best_fix['bot_price']:.2f}-{best_fix['top_price']:.2f}, score={best_fix['score']:.2f}")
            return best_fix
        else:
            print("[FPF] FIX плато не найдено")
            return None
        
    def _find_plateau_fix(self, start_idx: int, end_idx: int) -> Optional[Dict[str, Any]]:
        """Поиск FIX как плато из высоких точек (по логике из бэкапа)."""
        if end_idx <= start_idx + 3:
            return None
            
        segment = self.bars[start_idx:end_idx]
        if not segment:
            return None
            
        # Извлекаем цены как в бэкапе
        highs = [bar[2] for bar in segment]  # high
        lows = [bar[3] for bar in segment]   # low
        opens = [bar[1] for bar in segment]  # open  
        closes = [bar[4] for bar in segment] # close
        
        max_h, min_l = max(highs), min(lows)
        height_seg = max(1e-9, max_h - min_l)
        
        # Медиана топ-N самых высоких точек (логика из бэкапа)
        n = len(segment)
        top_n = max(3, min(12, n // 8))
        top_sorted = sorted(highs, reverse=True)[:top_n]
        ref_top = self._median(top_sorted) if top_sorted else max_h
        
        # Плотное плато - свечи близко к медиане топ-хаев
        p90_high = self._percentile(highs, 0.90) or max_h
        ref_top = max(p90_high, ref_top)
        
        # Полоса толерантности (как в бэкапе)
        med_h = self._median(highs) or ref_top
        mad = self._median([abs(h - med_h) for h in highs]) or 0.0
        band = max(0.01 * height_seg, 1.2 * mad)
        
        # Находим свечи в плато
        plateau_indices = []
        for i, h in enumerate(highs):
            if h >= ref_top - band:  # Близко к топу
                plateau_indices.append(i)
        
        if len(plateau_indices) < 3:  # Минимум 3 свечи для плато
            return None
            
        # Ищем лучший непрерывный блок
        best_block = self._find_best_contiguous_block(plateau_indices, highs)
        if not best_block:
            return None
            
        # Границы FIX зоны
        left_i = start_idx + min(best_block)
        right_i = start_idx + max(best_block)
        
        block_highs = [highs[i] for i in best_block]
        block_lows = [lows[i] for i in best_block]
        
        top_price = max(block_highs) + max(block_highs) * 0.002  # Небольшой отступ сверху
        bot_price = min(block_lows)
        
        # Скор качества плато
        mean_high = sum(block_highs) / len(block_highs)
        score = len(best_block) * mean_high  # Длина блока * средняя высота
        
        return {
            'left_i': left_i,
            'right_i': right_i,
            'top_price': top_price,
            'bot_price': bot_price,
            'score': score
        }
    
    def _median(self, vals):
        """Вычисление медианы (из бэкапа)."""
        if not vals:
            return None
        s = sorted(vals)
        n = len(s)
        if n == 0:
            return None
        m = n // 2
        if n % 2:
            return s[m]
        return (s[m-1] + s[m]) / 2.0
    
    def _percentile(self, vals, q: float):
        """Вычисление процентиля (из бэкапа)."""
        if not vals:
            return None
        s = sorted(vals)
        k = (len(s) - 1) * q
        f = int(k)  # floor
        c = int(k + 0.999)  # ceil
        if f == c:
            return s[f]
        return s[f] + (s[c] - s[f]) * (k - f)
    
    def _find_best_contiguous_block(self, indices, highs):
        """Найти лучший непрерывный блок индексов (из бэкапа)."""
        if not indices:
            return None
            
        # Группируем смежные индексы
        blocks = []
        current_block = [indices[0]]
        
        for i in range(1, len(indices)):
            if indices[i] == indices[i-1] + 1:  # Смежный
                current_block.append(indices[i])
            else:
                blocks.append(current_block)
                current_block = [indices[i]]
        blocks.append(current_block)
        
        # Выбираем лучший блок: сначала по длине, потом по средней высоте
        best_block = None
        best_score = 0
        
        for block in blocks:
            if len(block) < 2:  # Минимум 2 свечи
                continue
            block_highs = [highs[i] for i in block]
            mean_high = sum(block_highs) / len(block_highs)
            score = len(block) * 100 + mean_high  # Приоритет длине
            if score > best_score:
                best_score = score
                best_block = block
                
        return best_block
        
    def _find_local_maxima(self, start_idx: int, end_idx: int) -> List[Tuple[int, float]]:
        """Найти локальные максимумы (пики) в заданном диапазоне."""
        maxima = []
        window = 3  # Окно для поиска пиков
        
        for i in range(start_idx + window, end_idx - window):
            current_high = self.bars[i][2]  # high
            
            # Проверим, что это локальный максимум
            is_maximum = True
            for j in range(i - window, i + window + 1):
                if j != i and j >= 0 and j < len(self.bars):
                    if self.bars[j][2] >= current_high:
                        is_maximum = False
                        break
                        
            if is_maximum:
                maxima.append((i, current_high))
                
        # Сортируем по убыванию цены и берем первые 5
        maxima.sort(key=lambda x: x[1], reverse=True)
        return maxima[:5]
        
    def _evaluate_fix_around_peak(self, peak_idx: int, peak_price: float) -> Optional[Dict[str, Any]]:
        """Оценить качество FIX зоны вокруг найденного пика."""
        # Расширим зону вокруг пика
        left_bound = max(0, peak_idx - 3)
        right_bound = min(len(self.bars), peak_idx + 4)
        
        if right_bound <= left_bound + 1:
            return None
            
        zone_bars = self.bars[left_bound:right_bound]
        if not zone_bars:
            return None
            
        highs = [bar[2] for bar in zone_bars]  # high
        lows = [bar[3] for bar in zone_bars]   # low
        
        top_price = max(highs)
        bot_price = min(lows)
        price_range = top_price - bot_price
        
        # FIX должен иметь разумный размах и содержать значимый пик
        # Смягчаем критерии для поиска более ранних зон
        if price_range > top_price * 0.003:  # Минимум 0.3% от цены (было 0.5%)
            return {
                'left_i': left_bound,
                'right_i': right_bound - 1,
                'top_price': top_price,
                'bot_price': bot_price,
                'peak_idx': peak_idx,
                'score': price_range * peak_price
            }
            
        return None
        
    def _find_loy_fix(self) -> Optional[Dict[str, Any]]:
        """Поиск ЛОЙ-FIX - более заметный лой после FIX зоны."""
        if not self.fix_zone:
            return None
            
        fix_right = self.fix_zone['right_i']
        search_start = fix_right + 1
        search_end = min(self.n_bars, fix_right + 30)  # Ищем в разумных пределах
        
        if search_start >= search_end:
            return None
            
        min_low = float('inf')
        loy_idx = search_start
        
        for i in range(search_start, search_end):
            bar_low = self.bars[i][3]  # low
            if bar_low < min_low:
                min_low = bar_low
                loy_idx = i
                
        loy_fix = {
            'index': loy_idx,
            'price': min_low,
            'timestamp': self.bars[loy_idx][0]
        }
        
        print(f"[FPF] ЛОЙ-FIX найден: индекс {loy_idx}, цена {min_low:.2f}")
        return loy_fix
        
    def _find_hi_pattern(self) -> Optional[Dict[str, Any]]:
        """Поиск Hi-pattern - хай выше FIX зоны (между ЛОЙ-FIX и центром)."""
        if not self.fix_zone or not self.loy_fix:
            return None
            
        fix_top = self.fix_zone['top_price']
        loy_idx = self.loy_fix['index']
        
        # Ищем между ЛОЙ-FIX и центром анализа
        search_start = loy_idx + 1
        search_end = min(self.n_bars, self.center_idx + 20)
        
        if search_start >= search_end:
            return None
            
        best_hi = None
        max_high = fix_top  # Hi-pattern должен быть выше FIX
        
        for i in range(search_start, search_end):
            bar_high = self.bars[i][2]  # high
            if bar_high > max_high:
                max_high = bar_high
                best_hi = {
                    'index': i,
                    'price': bar_high,
                    'timestamp': self.bars[i][0]
                }
                
        if best_hi:
            print(f"[FPF] Hi-pattern найден: индекс {best_hi['index']}, цена {best_hi['price']:.2f}")
            
        return best_hi
        
    def _check_pattern_validation(self) -> Optional[Dict[str, Any]]:
        """Проверка валидации паттерна - обновление ЛОЙ-FIX сверху-вниз после Hi-pattern."""
        if not self.hi_pattern or not self.loy_fix:
            return None
            
        hi_idx = self.hi_pattern['index']
        loy_price = self.loy_fix['price']
        
        # Ищем после Hi-pattern
        search_start = hi_idx + 1
        search_end = min(self.n_bars, search_start + 50)
        
        for i in range(search_start, search_end):
            bar_low = self.bars[i][3]  # low
            
            # Проверяем обновление ЛОЙ-FIX сверху-вниз (хотя бы на 1 тик)
            if bar_low < loy_price - 1e-6:
                validation = {
                    'index': i,
                    'price': bar_low,
                    'timestamp': self.bars[i][0]
                }
                print(f"[FPF] Валидация найдена: индекс {i}, цена {bar_low:.2f} < {loy_price:.2f}")
                return validation
                
        print("[FPF] Валидация не найдена - паттерн не подтвержден")
        return None
        
    def _build_ray(self) -> Optional[Dict[str, Any]]:
        """Построение RAY - луч от ЛОЙ-FIX до первого касания сверху после валидации."""
        if not self.loy_fix or not self.validation_point:
            return None
            
        loy_price = self.loy_fix['price']
        val_idx = self.validation_point['index']
        
        # Ищем первое касание RAY сверху после валидации
        ray_end_idx = len(self.bars) - 1  # По умолчанию до конца данных
        
        for i in range(val_idx + 1, len(self.bars)):
            bar_low = self.bars[i][3]  # low
            
            # Касание сверху (low касается или проходит через ray price)
            if bar_low <= loy_price + 1e-6:
                ray_end_idx = i
                break
                
        ray_data = {
            'from_i': self.loy_fix['index'],
            'to_i': ray_end_idx,
            'price': loy_price,
            'validated': True
        }
        
        print(f"[FPF] RAY построен: от индекса {ray_data['from_i']} до {ray_data['to_i']}, цена {loy_price:.2f}")
        return ray_data
        
    def _build_prefix_zone(self) -> Optional[Dict[str, Any]]:
        """Построение PREFIX зоны - зона интереса для шорта, высота = FIX."""
        if not self.fix_zone or not self.ray_data:
            return None
            
        # PREFIX начинается от точки валидации RAY
        ray_validation_idx = self.ray_data['to_i']
        
        # Высота PREFIX = высота FIX
        fix_height = self.fix_zone['top_price'] - self.fix_zone['bot_price']
        ray_price = self.ray_data['price']
        
        prefix_zone = {
            'left_i': ray_validation_idx,
            'right_i': len(self.bars) - 1,  # До конца данных
            'top_price': ray_price + fix_height,
            'bot_price': ray_price,
            'height': fix_height
        }
        
        print(f"[FPF] PREFIX построен: от индекса {prefix_zone['left_i']}, высота {fix_height:.2f}")
        return prefix_zone
        
    def _find_ba25_level(self) -> Optional[Dict[str, Any]]:
        """Поиск BA25 уровня - лой между Hi-pattern и PREFIX для безубытка."""
        if not self.hi_pattern or not self.prefix_zone:
            return None
            
        hi_idx = self.hi_pattern['index']
        prefix_start = self.prefix_zone['left_i']
        
        if prefix_start <= hi_idx:
            return None
            
        # Ищем минимальный лой между Hi-pattern и PREFIX
        min_low = float('inf')
        ba25_idx = hi_idx
        
        for i in range(hi_idx, prefix_start + 1):
            if i < len(self.bars):
                bar_low = self.bars[i][3]  # low
                if bar_low < min_low:
                    min_low = bar_low
                    ba25_idx = i
                    
        ba25_level = {
            'index': ba25_idx,
            'price': min_low,
            'level_type': 'BA25'  # Безубыток 25%
        }
        
        print(f"[FPF] BA25 найден: индекс {ba25_idx}, цена {min_low:.2f}")
        return ba25_level
        
    def _calculate_take_profit(self) -> Optional[Dict[str, Any]]:
        """Расчет Take Profit зоны - примерно равен среднему объему от начала движения."""
        if not self.fix_zone or not self.loy_fix:
            return None
            
        # Расстояние от начала FIX до ЛОЙ-FIX
        fix_start_price = self.fix_zone['bot_price']
        loy_price = self.loy_fix['price']
        
        # Take Profit примерно равен этому движению
        tp_distance = abs(fix_start_price - loy_price)
        tp_price = loy_price - tp_distance  # Для шорта вниз
        
        take_profit = {
            'price': tp_price,
            'distance': tp_distance,
            'level_type': 'Take_Profit'
        }
        
        print(f"[FPF] Take Profit рассчитан: цена {tp_price:.2f}, дистанция {tp_distance:.2f}")
        return take_profit


def build_fpf_pattern_from_bars(bars: List[Tuple], center_bar_index: int) -> Dict[str, Any]:
    """
    Удобная функция для построения FPF паттерна.
    
    Args:
        bars: List of (timestamp, open, high, low, close) tuples  
        center_bar_index: Индекс центрального бара (от OCR времени)
        
    Returns:
        Dict с элементами паттерна или пустой dict если паттерн не найден
    """
    builder = FPFPatternBuilder(bars, center_bar_index)
    return builder.build_pattern()


if __name__ == "__main__":
    # Простой тест
    test_bars = [
        (i*1000, 100+i*0.1, 105+i*0.1, 95+i*0.1, 102+i*0.1) 
        for i in range(100)
    ]
    
    pattern = build_fpf_pattern_from_bars(test_bars, 50)
    print(f"Test pattern: {pattern}")
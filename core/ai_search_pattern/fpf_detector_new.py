#!/usr/bin/env python3
"""
ИСПРАВЛЕННЫЙ FPF Pattern Detector - исправлена логика OCR
Когда пользователь указывает OCR свечу - она является ЦЕНТРОМ FIX области
"""
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass


@dataclass
class CandleData:
    """Данные свечи"""
    timestamp: int
    open: float
    high: float 
    low: float
    close: float
    volume: float = 0
    
    @classmethod
    def from_tuple(cls, data: tuple):
        """Создает из кортежа (timestamp, open, high, low, close, volume)"""
        return cls(
            timestamp=int(data[0]),
            open=float(data[1]),
            high=float(data[2]), 
            low=float(data[3]),
            close=float(data[4]),
            volume=float(data[5]) if len(data) > 5 else 0
        )


@dataclass 
class FpfPattern:
    """Найденный FPF паттерн"""
    # FIX область
    fix_start_idx: int
    fix_end_idx: int
    fix_high: float
    fix_low: float
    
    # ЛОЙ-FIX
    loy_fix_idx: int
    loy_fix_price: float
    
    # HI-PATTERN
    hi_pattern_idx: int
    hi_pattern_price: float
    
    # RAY валидация
    ray_price: float
    ray_validated: bool
    
    # PREFIX область  
    prefix_start_price: float
    prefix_end_price: float
    
    # Дополнительная информация
    confidence: float
    ocr_candle_idx: Optional[int] = None


class FpfPatternDetector:
    """Детектор FPF паттернов по алгоритму из базы знаний"""
    
    def __init__(self, debug: bool = True):
        self.debug = debug
        
    def detect_pattern(self, candles: List[Any], ocr_candle_idx: Optional[int] = None) -> Optional[FpfPattern]:
        """
        Основной метод поиска FPF паттерна
        
        Args:
            candles: Список свечей (кортежи или объекты)
            ocr_candle_idx: Индекс свечи указанной пользователем через OCR (ЦЕНТР FIX)
            
        Returns:
            FpfPattern или None если паттерн не найден
        """
        if len(candles) < 50:
            self._log("Not enough candles for pattern detection")
            return None
            
        # Конвертируем данные в удобный формат
        candlesticks = self._convert_candles(candles)
        
        self._log(f"Analyzing {len(candlesticks)} candles, OCR candle: {ocr_candle_idx}")
        
        # ШАГ 1: Находим FIX область - если есть OCR, то OCR = ЦЕНТР FIX
        fix_area = None
        if ocr_candle_idx is not None:
            fix_area = self._find_fix_around_ocr(candlesticks, ocr_candle_idx)
            
        if not fix_area:
            # Резервный метод
            fix_area = self._find_fix_area(candlesticks, ocr_candle_idx)
            if not fix_area:
                self._log("No FIX area found")
                return None
        
        fix_start_idx, fix_end_idx, fix_center, fix_high, fix_low = fix_area
        self._log(f"✅ FIX area: indices {fix_start_idx}-{fix_end_idx}, prices {fix_low:.2f}-{fix_high:.2f}")
        
        # ШАГ 2: Ищем HI-PATTERN справа от FIX
        hi_pattern_data = self._find_hi_pattern_after_fix(candlesticks, fix_end_idx)
        if not hi_pattern_data:
            self._log("No HI-PATTERN found after FIX")
            return None
            
        hi_pattern_idx, hi_pattern_price = hi_pattern_data
        self._log(f"✅ HI-PATTERN: index {hi_pattern_idx}, price {hi_pattern_price:.2f}")
        
        # ШАГ 3: Ищем LOY-FIX между FIX и HI-PATTERN
        loy_fix_data = self._find_loy_fix_between(candlesticks, fix_end_idx, hi_pattern_idx)
        if not loy_fix_data:
            self._log("No LOY-FIX found between FIX and HI-PATTERN")
            return None
            
        loy_fix_idx, loy_fix_price = loy_fix_data
        self._log(f"✅ LOY-FIX: index {loy_fix_idx}, price {loy_fix_price:.2f}")
        
        # ШАГ 4: Валидация RAY (горизонтальная линия от LOY-FIX)
        ray_price = loy_fix_price
        ray_validated = self._validate_ray(candlesticks, loy_fix_idx, hi_pattern_idx, ray_price)
        
        self._log(f"✅ RAY validation: {ray_validated}, price {ray_price:.2f}")
        
        # ШАГ 5: Рассчитываем PREFIX область (только если RAY валидирован)
        if ray_validated:
            prefix_start_price = fix_low
            prefix_end_price = fix_high
        else:
            prefix_start_price = 0
            prefix_end_price = 0
            
        # Создаем паттерн
        pattern = FpfPattern(
            fix_start_idx=fix_start_idx,
            fix_end_idx=fix_end_idx,
            fix_high=fix_high,
            fix_low=fix_low,
            loy_fix_idx=loy_fix_idx,
            loy_fix_price=loy_fix_price,
            hi_pattern_idx=hi_pattern_idx,
            hi_pattern_price=hi_pattern_price,
            ray_price=ray_price,
            ray_validated=ray_validated,
            prefix_start_price=prefix_start_price,
            prefix_end_price=prefix_end_price,
            confidence=0.85,  # базовая уверенность
            ocr_candle_idx=ocr_candle_idx
        )
        
        self._log(f"FPF Pattern detected with confidence {pattern.confidence:.2f}")
        return pattern
        
    def _convert_candles(self, candles: List[Any]) -> List[CandleData]:
        """Конвертирует входные данные в CandleData"""
        result = []
        for candle in candles:
            if isinstance(candle, tuple):
                result.append(CandleData.from_tuple(candle))
            elif hasattr(candle, 'high'):
                result.append(candle)
            else:
                # Предполагаем что это словарь
                result.append(CandleData(
                    timestamp=candle.get('timestamp', 0),
                    open=candle['open'],
                    high=candle['high'], 
                    low=candle['low'],
                    close=candle['close'],
                    volume=candle.get('volume', 0)
                ))
        return result
        
    def _find_fix_around_ocr(self, candles: List[CandleData], ocr_idx: int) -> Optional[Tuple[int, int, float, float, float]]:
        """
        ИСПРАВЛЕНО: Поиск ТОЛЬКО ВЕРХНЕГО ПЛАТО FIX области вокруг OCR свечи
        OCR свеча = ЦЕНТР FIX области, но только ПЛОСКАЯ часть на вершине
        """
        self._log(f"🎯 Finding TOP PLATEAU FIX around OCR candle {ocr_idx}")
        
        # Сначала найдем максимальные цены в окрестности OCR
        search_window = 10  # расширенное окно для поиска пика
        search_start = max(0, ocr_idx - search_window)  
        search_end = min(len(candles), ocr_idx + search_window)
        
        # Находим локальный максимум в области
        max_price = 0
        for i in range(search_start, search_end):
            if candles[i].high > max_price:
                max_price = candles[i].high
                
        self._log(f"Local max price around OCR: {max_price:.4f}")
        
        # Более гибкий поиск плато на верхнем уровне
        plateau_tolerance = max_price * 0.015  # увеличено: 1.5% от пика
        min_plateau_price = max_price - plateau_tolerance
        
        self._log(f"Looking for plateau above {min_plateau_price:.4f} (tolerance {plateau_tolerance:.4f})")
        
        best_fix = None
        best_score = 0
        
        # Пробуем разные размеры плато
        for half_window in range(1, 6):  # меньшие окна для плато
            start_idx = max(0, ocr_idx - half_window)
            end_idx = min(len(candles) - 1, ocr_idx + half_window)
            
            # Должна включать OCR свечу
            if not (start_idx <= ocr_idx <= end_idx):
                continue
                
            # Анализируем это окно как потенциальное плато
            window_candles = candles[start_idx:end_idx+1]
            if len(window_candles) < 2:
                continue
                
            # Более гибкая проверка - большинство свечей должно быть в плато
            plateau_candles = 0
            for candle in window_candles:
                # Проверяем что закрытие свечи в диапазоне плато (более мягко)
                if candle.close >= min_plateau_price:
                    plateau_candles += 1
                    
            # Требуем чтобы минимум 70% свечей были в плато
            plateau_ratio = plateau_candles / len(window_candles)
            if plateau_ratio < 0.7:
                self._log(f"Window {start_idx}-{end_idx}: only {plateau_ratio*100:.0f}% candles in plateau")
                continue
            
            # Рассчитываем параметры плато
            highs = [c.high for c in window_candles]
            lows = [c.low for c in window_candles]
            
            fix_high = max(highs)
            fix_low = min(lows)
            fix_center = (fix_high + fix_low) / 2
            fix_height = fix_high - fix_low
            
            # Более мягкая проверка на плоскость плато
            volatility = fix_height / fix_center if fix_center > 0 else 1
            if volatility > 0.025:  # смягчено: максимум 2.5% волатильности
                self._log(f"Window {start_idx}-{end_idx}: too volatile {volatility*100:.2f}%")
                continue
                
            # Более мягкая проверка близости к пику
            distance_from_peak = abs(fix_center - max_price) / max_price
            if distance_from_peak > 0.02:  # смягчено: в пределах 2% от пика
                self._log(f"Window {start_idx}-{end_idx}: too far from peak {distance_from_peak*100:.2f}%")
                continue
                
            # Оценка плато
            score = 100 - (volatility * 5000)  # очень строго к волатильности
            
            # Бонус за близость к пику
            score += 50 * (1 - distance_from_peak * 100)  # чем ближе к пику, тем лучше
            
            # Бонус за центральное положение OCR
            center_pos = (start_idx + end_idx) / 2
            ocr_centrality = 1 - abs(center_pos - ocr_idx) / max(half_window, 1)
            score += 30 * ocr_centrality  # до 30 баллов за центральность
            
            # Предпочитаем компактные плато (3-6 свечей)
            window_size = end_idx - start_idx + 1
            if 3 <= window_size <= 6:
                score += 20
            elif window_size <= 4:
                score += 15
                
            self._log(f"TOP PLATEAU candidate {start_idx}-{end_idx}: volatility={volatility*100:.2f}%, peak_dist={distance_from_peak*100:.2f}%, score={score:.1f}")
                
            if score > best_score:
                best_score = score
                best_fix = (start_idx, end_idx, fix_center, fix_high, fix_low)
        
        if best_fix and best_score >= 50:  # снижен порог для более гибкой детекции
            start, end, center, high, low = best_fix
            self._log(f"✅ TOP PLATEAU FIX found: {start}-{end}, prices {low:.2f}-{high:.2f}, score={best_score:.1f}")
            return best_fix
        
        self._log("❌ No good TOP PLATEAU found around OCR")
        return None
        
    def _find_hi_pattern_after_fix(self, candles: List[CandleData], fix_end_idx: int) -> Optional[Tuple[int, float]]:
        """Ищет HI-PATTERN справа от FIX области"""
        search_start = fix_end_idx + 1
        search_end = min(len(candles), fix_end_idx + 50)  # не слишком далеко
        
        max_price = 0
        hi_pattern_idx = None
        
        for i in range(search_start, search_end):
            if candles[i].high > max_price:
                max_price = candles[i].high
                hi_pattern_idx = i
                
        if hi_pattern_idx:
            return (hi_pattern_idx, max_price)
        return None
        
    def _find_loy_fix_between(self, candles: List[CandleData], fix_end_idx: int, hi_pattern_idx: int) -> Optional[Tuple[int, float]]:
        """Ищет LOY-FIX между FIX и HI-PATTERN"""
        search_start = fix_end_idx + 1
        search_end = hi_pattern_idx
        
        min_price = float('inf')
        loy_fix_idx = None
        
        for i in range(search_start, search_end):
            if candles[i].low < min_price:
                min_price = candles[i].low
                loy_fix_idx = i
                
        if loy_fix_idx:
            return (loy_fix_idx, min_price)
        return None
        
    def _find_fix_area(self, candles: List[CandleData], ocr_idx: Optional[int]) -> Optional[Tuple[int, int, float, float, float]]:
        """Резервный метод поиска FIX области"""
        if ocr_idx is None:
            # Если нет OCR, ищем в последней трети графика
            search_start = len(candles) // 3
            search_end = int(len(candles) * 0.9)
        else:
            # Если есть OCR, ищем рядом с указанной свечой
            search_start = max(0, ocr_idx - 20)
            search_end = min(len(candles), ocr_idx + 20)
            
        self._log(f"Backup search for FIX area between {search_start} and {search_end}")
        
        best_fix = None
        best_score = 0
        
        # Ищем окна разного размера
        for window_size in range(3, 12):  # от 3 до 11 свечей
            for start_idx in range(search_start, search_end - window_size):
                end_idx = start_idx + window_size
                
                # Анализируем это окно как потенциальный FIX
                score = self._score_fix_area(candles, start_idx, end_idx, ocr_idx)
                
                if score > best_score:
                    best_score = score
                    
                    # Рассчитываем параметры FIX области
                    window_candles = candles[start_idx:end_idx]
                    fix_high = max(c.high for c in window_candles)
                    fix_low = min(c.low for c in window_candles)
                    center_price = (fix_high + fix_low) / 2
                    
                    best_fix = (start_idx, end_idx, center_price, fix_high, fix_low)
        
        if best_fix and best_score > 0.8:
            return best_fix
            
        return None
        
    def _score_fix_area(self, candles: List[CandleData], start_idx: int, end_idx: int, ocr_idx: Optional[int]) -> float:
        """Оценка FIX области"""
        window_candles = candles[start_idx:end_idx]
        if len(window_candles) < 3:
            return 0
            
        # Рассчитываем волатильность
        highs = [c.high for c in window_candles]
        lows = [c.low for c in window_candles]
        
        fix_high = max(highs)
        fix_low = min(lows)
        fix_center = (fix_high + fix_low) / 2
        fix_height = fix_high - fix_low
        
        volatility = fix_height / fix_center if fix_center > 0 else 1
        
        # Базовая оценка (низкая волатильность = высокий score)
        if volatility > 0.025:  # слишком высокая волатильность
            return 0
            
        score = 1.0 - volatility * 20  # чем ниже волатильность, тем выше score
        
        # Бонус за близость к OCR
        if ocr_idx is not None:
            center_pos = (start_idx + end_idx) / 2
            distance = abs(center_pos - ocr_idx)
            if distance <= 5:
                score += 0.3
            elif distance <= 10:
                score += 0.2
                
        return max(0, score)
        
    def _validate_ray(self, candles: List[CandleData], loy_fix_idx: int, hi_pattern_idx: int, ray_price: float) -> bool:
        """Валидация RAY - проверяет что цена не пробивала уровень LOY-FIX"""
        # Проверяем область после HI-PATTERN
        check_start = hi_pattern_idx + 1
        check_end = min(len(candles), hi_pattern_idx + 30)
        
        for i in range(check_start, check_end):
            if candles[i].low < ray_price:
                return False  # RAY пробит
                
        return True  # RAY не пробит - валидация успешна
        
    def _log(self, message: str):
        """Логирование"""
        if self.debug:
            print(f"[FPF] {message}")
# -*- coding: utf-8 -*-
"""
inference.py - AI pattern detection for FPF patterns

This module provides the detect_short_pattern function expected by tv_ingest_app.
"""

from typing import Dict, Any, List, Optional
import statistics


def detect_short_pattern(bars: List[Dict[str, Any]], meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect SHORT FPF pattern from candlestick data.
    
    Args:
        bars: List of bar dictionaries with keys: ts_open_ms, open, high, low, close, volume
        meta: Metadata dict with keys: symbol, timeframe, datetime
               Может содержать green_highlights - координаты зеленых выделений
    
    Returns:
        Dictionary with pattern elements:
        {
            'fix': {'left_i': int, 'right_i': int, 'top_price': float, 'bot_price': float},
            'ray': {'from_i': int, 'to_i': int, 'low_price': float}
        }
    """
    if not bars or len(bars) < 20:
        return {}
    
    print(f"[AI DEBUG] detect_short_pattern called with {len(bars)} bars, meta={meta}")
    print(f"[AI DEBUG] First bar: {bars[0] if bars else 'None'}")
    print(f"[AI DEBUG] Bar format: {type(bars[0]) if bars else 'None'}")
    
    try:
        # Проверяем есть ли зеленые выделения (маркировка пользователя)
        green_highlights = meta.get('green_highlights', [])
        
        if green_highlights:
            print(f"[AI DEBUG] Found {len(green_highlights)} green highlights from user")
            # Используем координаты зеленого выделения для поиска FIX свечи
            fix_result = _detect_fix_from_green_highlight(bars, green_highlights[0])
        else:
            print("[AI DEBUG] No green highlights, using smart FIX detection")
            # Используем умный поиск FIX - сначала ищем все возможные плато, 
            # потом выбираем лучшее на основе OCR времени или других признаков
            ocr_datetime = meta.get('datetime', '')
            if ocr_datetime:
                # Комбинированный подход: ищем плато + уточняем по OCR времени
                fix_result = _smart_fix_detection(bars, meta)
            else:
                # Fallback на автоматический поиск лучшего плато
                fix_result = _detect_fix_area(bars)
        
        ray_result = _detect_ray_from_fix(bars, fix_result) if fix_result else None
        
        result = {}
        if fix_result:
            result['fix'] = fix_result
            print(f"[AI DEBUG] FIX detected: {fix_result}")
        if ray_result:
            result['ray'] = ray_result
            print(f"[AI DEBUG] RAY detected: {ray_result}")
            
        return result
        
    except Exception as e:
        print(f"[AI ERROR] Pattern detection failed: {e}")
        return {}


def _detect_fix_area(bars: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Detect FIX area - consolidation plateau AFTER major impulse move up.
    
    FIX логика для SHORT паттерна:
    1. Находим сильные импульсы вверх во всем диапазоне
    2. После каждого импульса ищем плато консолидации (низкая волатильность)
    3. FIX = плато с маленькими свечами на вершине
    """
    if len(bars) < 20:
        return None
    
    best_fix = None
    best_score = 0
    
    # Ищем во всем диапазоне - от 30% до 90%
    search_start = int(len(bars) * 0.3)
    search_end = int(len(bars) * 0.9)
    
    # Сначала находим все сильные импульсы вверх
    impulse_peaks = _find_impulse_peaks(bars, search_start, search_end)
    
    print(f"[AI DEBUG] Found {len(impulse_peaks)} impulse peaks")
    
    # После каждого импульса ищем зону консолидации  
    # Увеличиваем размер окна для 15m таймфрейма
    window_size = max(5, min(8, len(bars) // 40))  # Окна 5-8 свечей для лучшей детекции
    
    for peak_idx in impulse_peaks:
        # Ищем консолидацию в зоне после пика
        consolidation_start = peak_idx + 2  # Начинаем через 2 бара после пика
        consolidation_end = min(len(bars) - window_size, peak_idx + 25)  # В пределах 25 баров
        
        if consolidation_start >= consolidation_end:
            continue
            
        for i in range(consolidation_start, consolidation_end):
            window_bars = bars[i:i + window_size]
            
            # Извлекаем цены из баров
            highs = []
            lows = []
            closes = []
            
            for bar in window_bars:
                if isinstance(bar, dict):
                    highs.append(bar['high'])
                    lows.append(bar['low'])
                    closes.append(bar['close'])
                else:
                    highs.append(bar[2])  # high
                    lows.append(bar[3])   # low
                    closes.append(bar[4])  # close
            
            if not highs or not lows or not closes:
                continue
                
            # Рассчитываем характеристики консолидации
            range_high = max(highs)
            range_low = min(lows)
            range_size = range_high - range_low
            avg_close = statistics.mean(closes)
            
            if avg_close <= 0:
                continue
                
            range_pct = range_size / avg_close
            
            # Проверяем что это действительно плато (высокий уровень цен)
            peak_price = _get_peak_price(bars, peak_idx)
            plateau_price = avg_close
            
            # Плато должно быть близко к пику (не более 3% просадки)
            if peak_price > 0:
                drawdown = (peak_price - plateau_price) / peak_price
                if drawdown > 0.03:  # Больше 3% просадки - не плато
                    continue
            
            # FIX критерии:
            # 1. Очень низкая волатильность (плато)
            # 2. Высокий уровень цен (близко к пику)
            # 3. Компактная зона
            
            if range_pct < 0.008:  # Максимум 0.8% волатильность для КРОШЕЧНОГО плато!
                plateau_quality = 1.0 / (1.0 + range_pct * 100)
                height_score = 1.0 / (1.0 + drawdown * 50) if peak_price > 0 else 0.5
                
                total_score = plateau_quality * height_score
                
                if total_score > best_score:
                    best_score = total_score
                    best_fix = {
                        'left_i': i,
                        'right_i': i + window_size - 1,
                        'top_price': range_high,
                        'bot_price': range_low,
                        'score': total_score,
                        'range_pct': range_pct,
                        'drawdown': drawdown,
                        'peak_idx': peak_idx
                    }
                    
                    print(f"[AI DEBUG] Found FIX plateau: i={i}, range_pct={range_pct:.3f}, drawdown={drawdown:.3f}, score={total_score:.3f}")
    
    return best_fix


def _smart_fix_detection(bars: List[Dict[str, Any]], meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Умный поиск FIX плато с учетом времени OCR и анализа всех возможных зон.
    
    Логика:
    1. Находим ВСЕ возможные зоны консолидации (плато) в правой части графика
    2. Анализируем каждую зону по качеству (размер свечей, высота, компактность)  
    3. Если есть OCR время - отдаем предпочтение плато рядом с этой свечой
    4. Выбираем лучшее плато по общему скору
    """
    print("[AI DEBUG] Smart FIX detection: analyzing all potential plateaus")
    
    if len(bars) < 20:
        return None
    
    # Ищем по всему графику, а не только в правой части!
    search_start = 10
    search_end = len(bars) - 10
    
    plateau_candidates = []
    window_size = 6  # Компактные окна для плато
    
    # Находим целевую свечу из OCR (если есть)
    ocr_target_idx = None
    try:
        ocr_datetime_str = meta.get('datetime', '')
        if ocr_datetime_str:
            import datetime as dt
            ocr_dt = dt.datetime.strptime(ocr_datetime_str, '%Y-%m-%d %H:%M')
            ocr_timestamp = int(ocr_dt.timestamp() * 1000)
            
            min_time_diff = float('inf')
            for i, bar in enumerate(bars):
                bar_timestamp = bar[0] if isinstance(bar, tuple) else bar['ts_open_ms']
                time_diff = abs(bar_timestamp - ocr_timestamp)
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    ocr_target_idx = i
            
            print(f"[AI DEBUG] OCR target candle at index {ocr_target_idx}")
    except Exception as e:
        print(f"[AI DEBUG] OCR target detection failed: {e}")
    
    # Сканируем ВСЕ возможные плато по всему диапазону
    print(f"[AI DEBUG] Scanning for plateaus from {search_start} to {search_end}, window_size={window_size}")
    for i in range(search_start, search_end - window_size):
        plateau_data = _analyze_plateau_quality(bars, i, i + window_size)
        if plateau_data and plateau_data['quality_score'] > 0.3:  # Только качественные плато
            # Убираем привязку к OCR - ищем лучший паттерн по качеству
            # OCR служит только для информации, не влияет на выбор
            plateau_data['ocr_bonus'] = 0.0
                
            plateau_candidates.append(plateau_data)
            print(f"[AI DEBUG] Plateau candidate at {i}-{i+window_size}: score={plateau_data['total_score']:.3f}, quality={plateau_data['quality_score']:.3f}")
    
    if not plateau_candidates:
        print("[AI DEBUG] No plateau candidates found")
        return None
    
    # УМНАЯ ЛОГИКА: ПОЛЬЗОВАТЕЛЬ КЛИКНУЛ НА ВЕРШИНУ ПОСЛЕ ВОСХОДЯЩЕГО ДВИЖЕНИЯ
    # ПРОВЕРЯЕМ КАЧЕСТВО FIX РЯДОМ С OCR С УЧЕТОМ КОНТЕКСТА
    
    print(f"[AI DEBUG] *** ANALYZING CONTEXT AROUND OCR POSITION {ocr_target_idx} ***")
    
    # 1. ПРОВЕРЯЕМ ВОСХОДЯЩЕЕ ДВИЖЕНИЕ ПЕРЕД OCR
    uptrend_confirmed = _check_uptrend_before_ocr(bars, ocr_target_idx)
    
    # 2. ИЩЕМ ЛУЧШИЙ FIX В РАДИУСЕ ±5 СВЕЧЕЙ ОТ OCR С ПРОВЕРКАМИ КАЧЕСТВА
    best_plateau = None
    best_score = -1
    
    for window_size in range(2, 8):  # от 2 до 7 свечей
        for start in range(max(0, ocr_target_idx - 5), min(len(bars) - window_size, ocr_target_idx + 6)):
            end = start + window_size
            
            # Центр окна должен быть близко к OCR
            window_center = (start + end) // 2
            distance_to_ocr = abs(window_center - ocr_target_idx)
            
            if distance_to_ocr <= 3:  # в радиусе ±3 свечи от OCR
                # Анализируем качество этого FIX кандидата
                fix_quality = _analyze_fix_context(bars, start, end, ocr_target_idx, uptrend_confirmed)
                
                if fix_quality and fix_quality['total_score'] > best_score:
                    best_score = fix_quality['total_score']
                    best_plateau = fix_quality
                    print(f"[AI DEBUG] *** QUALITY FIX CANDIDATE: {start}-{end}, score={fix_quality['total_score']:.3f}, volatility={fix_quality.get('volatility', 0):.3f}% ***")
    
    if not best_plateau:
        print(f"[AI DEBUG] *** NO VALID FIX FOUND NEAR OCR {ocr_target_idx} - CONTEXT FAILED ***")
        return None
        
    print(f"[AI DEBUG] *** SELECTED CONTEXT-BASED FIX: {best_plateau['left_i']}-{best_plateau['right_i']}, score={best_plateau['total_score']:.3f} ***")
    
    return {
        'left_i': best_plateau['left_i'],
        'right_i': best_plateau['right_i'], 
        'top_price': best_plateau['top_price'],
        'bot_price': best_plateau['bot_price'],
        'center_candle_index': best_plateau['center_idx'],
        'range_pct': best_plateau['range_pct'],
        'method': 'smart_detection'
    }


def _analyze_plateau_quality(bars: List[Dict[str, Any]], start_idx: int, end_idx: int) -> Optional[Dict[str, Any]]:
    """
    Анализирует качество потенциального плато в заданном диапазоне.
    
    Возвращает словарь с метриками качества или None если не плато.
    """
    if start_idx >= end_idx or end_idx > len(bars):
        return None
    
    plateau_bars = bars[start_idx:end_idx]
    
    # Извлекаем данные свечей
    highs = []
    lows = []
    ranges = []
    
    for bar in plateau_bars:
        if isinstance(bar, tuple):
            high, low = bar[2], bar[3]
        else:
            high, low = bar['high'], bar['low']
        highs.append(high)
        lows.append(low)
        ranges.append(high - low)
    
    if not highs:
        return None
    
    plateau_high = max(highs)
    plateau_low = min(lows)
    avg_range = sum(ranges) / len(ranges)
    avg_price = (plateau_high + plateau_low) / 2
    
    # Критерии качества плато:
    # 1. Маленькие свечи (низкая средняя волатильность)
    avg_volatility = avg_range / avg_price if avg_price > 0 else 1.0
    
    # 2. Высокий уровень (плато должно быть на вершине)
    max_high_in_area = _get_max_high_in_area(bars, max(0, start_idx - 30), min(len(bars), end_idx + 30))
    height_ratio = avg_price / max_high_in_area if max_high_in_area > 0 else 0.0
    
    # 3. Компактность (маленький общий диапазон) 
    total_range = plateau_high - plateau_low
    compactness = 1.0 / (1.0 + total_range / avg_price * 100)
    
    # Фильтры качества - если не проходит, возвращаем None
    if avg_volatility > 0.015:  # Средняя волатильность свечей больше 1.5%
        return None
    if height_ratio < 0.95:     # Не на вершине (ниже 95% от максимума)
        return None
    if total_range / avg_price > 0.008:  # Общий диапазон больше 0.8%
        return None
        
    # Считаем общий скор качества
    volatility_score = 1.0 / (1.0 + avg_volatility * 100)  # Чем меньше волатильность, тем лучше
    height_score = height_ratio  # Чем выше, тем лучше
    compactness_score = compactness  # Чем компактнее, тем лучше
    
    quality_score = (volatility_score + height_score + compactness_score) / 3
    
    return {
        'left_i': start_idx,
        'right_i': end_idx - 1,
        'center_idx': (start_idx + end_idx) // 2,
        'top_price': plateau_high,
        'bot_price': plateau_high - plateau_high * 0.005,  # Компактная высота
        'range_pct': total_range / avg_price,
        'quality_score': quality_score,
        'total_score': quality_score,  # Пока равно quality_score, OCR бонус добавится позже
        'avg_volatility': avg_volatility,
        'height_ratio': height_ratio,
        'compactness': compactness
    }


def _check_uptrend_before_ocr(bars: List[Dict[str, Any]], ocr_idx: int, lookback: int = 20) -> bool:
    """
    Проверяет есть ли восходящее движение перед OCR позицией.
    """
    if ocr_idx < lookback:
        return False
        
    start_idx = ocr_idx - lookback
    end_idx = ocr_idx
    
    # Получаем цены закрытия
    closes = []
    for i in range(start_idx, end_idx):
        if isinstance(bars[i], tuple):
            closes.append(bars[i][4])  # close
        else:
            closes.append(bars[i]['close'])
    
    if len(closes) < 10:
        return False
    
    # Проверяем тренд: цена в конце должна быть значительно выше чем в начале
    start_price = sum(closes[:5]) / 5  # средняя из первых 5
    end_price = sum(closes[-5:]) / 5   # средняя из последних 5
    
    uptrend_strength = (end_price - start_price) / start_price
    
    print(f"[AI DEBUG] Uptrend check: start_price={start_price:.2f}, end_price={end_price:.2f}, strength={uptrend_strength:.3f}")
    
    # Требуем минимум 2% роста для подтверждения восходящего тренда
    return uptrend_strength > 0.02


def _analyze_fix_context(bars: List[Dict[str, Any]], start_idx: int, end_idx: int, ocr_idx: int, uptrend_confirmed: bool) -> Optional[Dict[str, Any]]:
    """
    Анализирует качество FIX кандидата с учетом контекста.
    """
    if start_idx >= end_idx or end_idx > len(bars):
        return None
    
    fix_bars = bars[start_idx:end_idx]
    
    # Извлекаем данные свечей
    highs = []
    lows = []
    closes = []
    
    for bar in fix_bars:
        if isinstance(bar, tuple):
            high, low, close = bar[2], bar[3], bar[4]
        else:
            high, low, close = bar['high'], bar['low'], bar['close']
        highs.append(high)
        lows.append(low)
        closes.append(close)
    
    if not highs:
        return None
    
    fix_high = max(highs)
    fix_low = min(lows)
    avg_price = (fix_high + fix_low) / 2
    
    # 1. ПРОВЕРКА ВОЛАТИЛЬНОСТИ (маленькие свечи)
    avg_candle_range = sum([(h - l) for h, l in zip(highs, lows)]) / len(highs)
    volatility = avg_candle_range / avg_price if avg_price > 0 else 1.0
    
    # 2. ПРОВЕРКА РАЗМЕРА ПЛАТО (компактность)
    plateau_range = fix_high - fix_low
    compactness = plateau_range / avg_price if avg_price > 0 else 1.0
    
    # 3. ПРОВЕРКА ПОЗИЦИИ НА ВЕРШИНЕ
    # Сравниваем с ценами в окрестности
    context_start = max(0, start_idx - 10)
    context_end = min(len(bars), end_idx + 10)
    context_bars = bars[context_start:context_end]
    
    max_high_around = 0
    for bar in context_bars:
        if isinstance(bar, tuple):
            bar_high = bar[2]
        else:
            bar_high = bar['high']
        max_high_around = max(max_high_around, bar_high)
    
    height_ratio = avg_price / max_high_around if max_high_around > 0 else 0
    
    # КРИТЕРИИ ОТБОРА
    score = 0
    
    # Бонус за низкую волатильность (маленькие свечи)
    if volatility < 0.01:  # менее 1%
        score += 3.0
    elif volatility < 0.015:  # менее 1.5%
        score += 2.0
    elif volatility < 0.02:  # менее 2%
        score += 1.0
    else:
        return None  # слишком волатильно для FIX
    
    # Бонус за компактность плато
    if compactness < 0.005:  # менее 0.5%
        score += 3.0
    elif compactness < 0.008:  # менее 0.8%
        score += 2.0
    elif compactness < 0.012:  # менее 1.2%
        score += 1.0
    else:
        return None  # слишком большой диапазон для FIX
    
    # Бонус за позицию на вершине
    if height_ratio > 0.98:  # очень близко к максимуму
        score += 3.0
    elif height_ratio > 0.95:  # близко к максимуму
        score += 2.0
    elif height_ratio > 0.90:  # неплохая позиция
        score += 1.0
    else:
        return None  # не на вершине
    
    # Огромный бонус за подтвержденный восходящий тренд
    if uptrend_confirmed:
        score += 5.0
    
    # Бонус за близость к OCR
    distance_to_ocr = abs((start_idx + end_idx) // 2 - ocr_idx)
    ocr_bonus = max(0, (5 - distance_to_ocr) / 5.0) * 2.0
    score += ocr_bonus
    
    print(f"[AI DEBUG] FIX analysis {start_idx}-{end_idx}: volatility={volatility:.3f}, compactness={compactness:.3f}, height_ratio={height_ratio:.3f}, uptrend={uptrend_confirmed}")
    
    return {
        'left_i': start_idx,
        'right_i': end_idx,
        'center_idx': (start_idx + end_idx) // 2,
        'top_price': fix_high,
        'bot_price': fix_low,
        'range_pct': compactness,
        'volatility': volatility * 100,  # в процентах
        'height_ratio': height_ratio,
        'uptrend_confirmed': uptrend_confirmed,
        'total_score': score
    }


def _get_max_high_in_area(bars: List[Dict[str, Any]], start_idx: int, end_idx: int) -> float:
    """Находит максимальный high в заданной области."""
    max_high = 0.0
    for i in range(max(0, start_idx), min(len(bars), end_idx)):
        bar = bars[i]
        high = bar[2] if isinstance(bar, tuple) else bar['high']
        max_high = max(max_high, high)
    return max_high


def _detect_fix_from_ocr_time(bars: List[Dict[str, Any]], meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Определяет FIX зону по времени из OCR (пользователь кликнул на свечу).
    
    OCR время указывает на конкретную свечу, вокруг которой нужно искать плато FIX.
    """
    print("[AI DEBUG] Using OCR time hint for FIX detection")
    
    try:
        import datetime as dt
        
        # Парсим время из OCR
        ocr_datetime_str = meta.get('datetime', '')
        print(f"[AI DEBUG] OCR datetime: {ocr_datetime_str}")
        
        if not ocr_datetime_str:
            return None
            
        # Конвертируем в timestamp для поиска в данных
        try:
            ocr_dt = dt.datetime.strptime(ocr_datetime_str, '%Y-%m-%d %H:%M')
            ocr_timestamp = int(ocr_dt.timestamp() * 1000)  # в миллисекундах
            print(f"[AI DEBUG] Looking for timestamp: {ocr_timestamp}")
        except:
            print("[AI ERROR] Failed to parse OCR datetime")
            return None
        
        # Ищем свечу ближайшую к указанному времени
        target_index = None
        min_time_diff = float('inf')
        
        for i, bar in enumerate(bars):
            bar_timestamp = bar[0] if isinstance(bar, tuple) else bar['ts_open_ms']
            time_diff = abs(bar_timestamp - ocr_timestamp)
            
            if time_diff < min_time_diff:
                min_time_diff = time_diff
                target_index = i
        
        if target_index is None:
            print("[AI ERROR] Could not find matching candle for OCR time")
            return None
            
        print(f"[AI DEBUG] Found target candle at index {target_index}")
        
        # Ищем плато консолидации вокруг указанной свечи
        return _build_fix_around_target(bars, target_index)
        
    except Exception as e:
        print(f"[AI ERROR] OCR time processing failed: {e}")
        return None


def _build_fix_around_target(bars: List[Dict[str, Any]], target_idx: int) -> Optional[Dict[str, Any]]:
    """
    Строит FIX зону вокруг указанной пользователем свечи.
    
    Логика:
    1. Находим цену указанной свечи
    2. Ищем соседние свечи в том же ценовом диапазоне
    3. Строим FIX зону вокруг этой области консолидации
    """
    if target_idx < 0 or target_idx >= len(bars):
        return None
    
    # Получаем цену центральной свечи
    center_bar = bars[target_idx]
    if isinstance(center_bar, tuple):
        center_high = center_bar[2]
        center_low = center_bar[3]
    else:
        center_high = center_bar['high']
        center_low = center_bar['low']
        
    center_price = (center_high + center_low) / 2
    
    print(f"[AI DEBUG] Building FIX around target index {target_idx}, price {center_price:.2f}")
    
    # Для плато FIX ищем зону с МАЛЕНЬКИМИ свечами (низкая волатильность)
    # Фокусируемся на верхней части ценового диапазона
    
    # Находим самые высокие цены в окрестности для определения плато
    window_start = max(0, target_idx - 10)
    window_end = min(len(bars), target_idx + 10)
    nearby_highs = []
    
    for i in range(window_start, window_end):
        bar = bars[i]
        bar_high = bar[2] if isinstance(bar, tuple) else bar['high']
        nearby_highs.append(bar_high)
    
    # Плато должно быть очень близко к максимальной цене (строже критерии)
    max_nearby = max(nearby_highs)
    plateau_threshold = max_nearby * 0.995  # В пределах 0.5% от пика (строже!)
    
    print(f"[AI DEBUG] Looking for tight plateau near {max_nearby:.2f}, threshold {plateau_threshold:.2f}")
    
    # Ищем ОЧЕНЬ КОМПАКТНОЕ плато - только самые маленькие свечи на вершине
    left_bound = target_idx
    right_bound = target_idx
    
    # Поиск влево - только крошечные свечи на самой вершине
    for i in range(target_idx - 1, max(0, target_idx - 6), -1):  # Уменьшаем поиск до 6 свечей
        bar = bars[i]
        bar_high = bar[2] if isinstance(bar, tuple) else bar['high']
        bar_low = bar[3] if isinstance(bar, tuple) else bar['low']
        bar_range = bar_high - bar_low
        bar_mid = (bar_high + bar_low) / 2
        
        # СТРОГИЕ условия для плато: очень высокая цена + очень маленький размер свечи
        is_very_high_level = bar_mid > plateau_threshold  # В пределах 0.5% от пика
        is_tiny_candle = bar_range < center_price * 0.008  # Максимум 0.8% размер свечи (очень строго!)
        
        if is_very_high_level and is_tiny_candle:
            left_bound = i
        else:
            break
    
    # Поиск вправо - только крошечные свечи на самой вершине
    for i in range(target_idx + 1, min(len(bars), target_idx + 6)):  # Уменьшаем поиск до 6 свечей
        bar = bars[i]
        bar_high = bar[2] if isinstance(bar, tuple) else bar['high']
        bar_low = bar[3] if isinstance(bar, tuple) else bar['low']
        bar_range = bar_high - bar_low
        bar_mid = (bar_high + bar_low) / 2
        
        is_very_high_level = bar_mid > plateau_threshold
        is_tiny_candle = bar_range < center_price * 0.008  # Очень строго
        
        if is_very_high_level and is_tiny_candle:
            right_bound = i
        else:
            break
    
    # Рассчитываем КОМПАКТНЫЕ границы FIX зоны - только верхняя часть диапазона
    fix_bars = bars[left_bound:right_bound + 1]
    
    if isinstance(fix_bars[0], tuple):
        fix_highs = [bar[2] for bar in fix_bars]  # high  
        fix_lows = [bar[3] for bar in fix_bars]   # low
    else:
        fix_highs = [bar['high'] for bar in fix_bars]
        fix_lows = [bar['low'] for bar in fix_bars]
        
    fix_high = max(fix_highs)
    
    # Для плато используем не самый низкий лой, а уровень близкий к верхней части
    # FIX должен быть плоским прямоугольником, а не покрывать весь диапазон движения
    fix_low = fix_high - (fix_high * 0.005)  # FIX высотой всего 0.5% от цены
    
    print(f"[AI DEBUG] Compact FIX zone: {fix_high:.2f} - {fix_low:.2f} (height: {(fix_high-fix_low)/fix_high*100:.2f}%)")
    
    fix_result = {
        'left_i': left_bound,
        'right_i': right_bound,
        'top_price': fix_high,
        'bot_price': fix_low,
        'target_index': target_idx,
        'range_pct': (fix_high - fix_low) / center_price,
        'method': 'ocr_time_hint'
    }
    
    print(f"[AI DEBUG] Built FIX from OCR hint: left={left_bound}, right={right_bound}, range={fix_high:.2f}-{fix_low:.2f}")
    
    return fix_result


def _find_impulse_peaks(bars: List[Dict[str, Any]], start_idx: int, end_idx: int) -> List[int]:
    """
    Находит индексы пиков после сильных импульсов вверх.
    """
    peaks = []
    
    # Ищем локальные максимумы с сильным импульсом перед ними
    for i in range(start_idx + 10, end_idx - 5):
        current_high = bars[i][2] if isinstance(bars[i], tuple) else bars[i]['high']
        
        # Проверяем что это локальный максимум
        is_peak = True
        for j in range(max(0, i-5), min(len(bars), i+6)):
            if j != i:
                other_high = bars[j][2] if isinstance(bars[j], tuple) else bars[j]['high']
                if other_high > current_high:
                    is_peak = False
                    break
        
        if not is_peak:
            continue
            
        # Проверяем силу импульса перед пиком
        impulse_strength = _calculate_impulse_before_zone(bars, i)
        if impulse_strength > 0.03:  # Минимум 3% импульс
            peaks.append(i)
    
    return peaks


def _get_peak_price(bars: List[Dict[str, Any]], peak_idx: int) -> float:
    """
    Получает цену пика.
    """
    if peak_idx >= len(bars):
        return 0.0
    
    bar = bars[peak_idx]
    if isinstance(bar, tuple):
        return float(bar[2])  # high
    else:
        return float(bar['high'])


def _calculate_impulse_before_zone(bars: List[Dict[str, Any]], end_idx: int) -> float:
    """
    Рассчитывает силу импульса ПЕРЕД заданной позицией (для FIX на вершине).
    """
    if end_idx < 15:
        return 0.0
    
    # Смотрим на предыдущие 15-20 баров перед FIX зоной
    start_idx = max(0, end_idx - 20)
    impulse_bars = bars[start_idx:end_idx]
    
    if len(impulse_bars) < 3:
        return 0.0
    
    # Находим максимальный и минимальный уровни в зоне импульса
    highs = []
    lows = []
    
    for bar in impulse_bars:
        if isinstance(bar, dict):
            highs.append(bar['high'])
            lows.append(bar['low'])
        else:
            highs.append(bar[2])  # high
            lows.append(bar[3])   # low
    
    if not highs or not lows:
        return 0.0
    
    impulse_high = max(highs)
    impulse_low = min(lows)
    impulse_range = impulse_high - impulse_low
    
    # Начальная цена (первый close в зоне импульса)
    if isinstance(impulse_bars[0], dict):
        start_price = impulse_bars[0]['close']
    else:
        start_price = impulse_bars[0][4]  # close
    
    if start_price == 0:
        return 0.0
    
    # Сила импульса = размер движения относительно начальной цены
    impulse_strength = impulse_range / start_price
    
    return impulse_strength


def _calculate_impulse_after_zone(bars: List[Dict[str, Any]], start_idx: int) -> float:
    """
    Рассчитывает силу импульса после заданной позиции.
    Импульс = большое движение цены за короткое время.
    """
    if start_idx >= len(bars) - 3:
        return 0.0
    
    # Смотрим на следующие 10-20 баров после FIX зоны
    end_idx = min(len(bars), start_idx + 15)
    impulse_bars = bars[start_idx:end_idx]
    
    if len(impulse_bars) < 3:
        return 0.0
    
    # Находим максимальный и минимальный уровни в зоне импульса
    highs = []
    lows = []
    
    for bar in impulse_bars:
        if isinstance(bar, dict):
            highs.append(bar['high'])
            lows.append(bar['low'])
        else:
            highs.append(bar[2])  # high
            lows.append(bar[3])   # low
    
    if not highs or not lows:
        return 0.0
    
    impulse_high = max(highs)
    impulse_low = min(lows)
    impulse_range = impulse_high - impulse_low
    
    # Начальная цена (первый close в зоне импульса)
    if isinstance(impulse_bars[0], dict):
        start_price = impulse_bars[0]['close']
    else:
        start_price = impulse_bars[0][4]  # close
    
    if start_price == 0:
        return 0.0
    
    # Сила импульса = размер движения относительно начальной цены
    impulse_strength = impulse_range / start_price
    
    return impulse_strength


def _detect_fix_from_green_highlight(bars: List[Dict[str, Any]], green_box: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Строит FIX зону от координат зеленого выделения пользователя.
    
    Логика:
    1. Конвертируем координаты выделения в индекс свечи на графике
    2. Находим соседние свечи того же ценового уровня (консолидация)  
    3. Строим FIX зону вокруг этой области
    
    Args:
        bars: список свечей
        green_box: координаты зеленого выделения {'center_x': int, 'center_y': int, ...}
    """
    if not bars or not green_box:
        return None
    
    print(f"[AI DEBUG] Building FIX from green highlight: {green_box}")
    
    try:
        # ШАГИ КОНВЕРТАЦИИ КООРДИНАТ В ИНДЕКС СВЕЧИ:
        
        # 1. Предполагаем что chart занимает основную часть скриншота
        # Обычно TradingView: левый отступ ~80px, правый ~50px, 
        # верхний ~100px, нижний ~50px для интерфейса
        
        chart_left_margin = 80
        chart_right_margin = 50  
        chart_width_pixels = 1200 - chart_left_margin - chart_right_margin  # примерная ширина чарта
        
        # 2. X координата зеленого выделения относительно чарта
        green_x_rel = green_box['center_x'] - chart_left_margin
        
        # 3. Конвертируем X в индекс свечи
        # Предполагаем что свечи распределены равномерно по ширине чарта
        bars_count = len(bars)
        candle_index = int((green_x_rel / chart_width_pixels) * bars_count)
        
        # Ограничиваем индекс в разумных пределах
        candle_index = max(0, min(candle_index, bars_count - 1))
        
        print(f"[AI DEBUG] Green highlight X={green_box['center_x']} -> candle_index={candle_index}")
        
        # 4. Находим цену выделенной свечи
        center_candle = bars[candle_index] 
        if isinstance(center_candle, dict):
            center_price = (center_candle['high'] + center_candle['low']) / 2
        else:
            center_price = (center_candle[2] + center_candle[3]) / 2  # (high + low) / 2
            
        print(f"[AI DEBUG] Center candle price: {center_price}")
        
        # 5. Ищем соседние свечи в том же ценовом диапазоне (консолидация)
        price_tolerance = center_price * 0.015  # 1.5% толерантность
        
        # Ищем влево от центральной свечи
        left_bound = candle_index
        for i in range(candle_index - 1, max(0, candle_index - 20), -1):
            bar = bars[i]
            bar_high = bar['high'] if isinstance(bar, dict) else bar[2]
            bar_low = bar['low'] if isinstance(bar, dict) else bar[3]
            
            # Проверяем пересекается ли свеча с нашим ценовым диапазоном
            if (bar_low <= center_price + price_tolerance and 
                bar_high >= center_price - price_tolerance):
                left_bound = i
            else:
                break  # Вышли из зоны консолидации
                
        # Ищем вправо от центральной свечи  
        right_bound = candle_index
        for i in range(candle_index + 1, min(len(bars), candle_index + 20)):
            bar = bars[i]
            bar_high = bar['high'] if isinstance(bar, dict) else bar[2]
            bar_low = bar['low'] if isinstance(bar, dict) else bar[3]
            
            if (bar_low <= center_price + price_tolerance and 
                bar_high >= center_price - price_tolerance):
                right_bound = i
            else:
                break
                
        # 6. Рассчитываем границы FIX зоны
        fix_bars = bars[left_bound:right_bound + 1]
        
        if isinstance(fix_bars[0], dict):
            fix_highs = [bar['high'] for bar in fix_bars]
            fix_lows = [bar['low'] for bar in fix_bars]  
        else:
            fix_highs = [bar[2] for bar in fix_bars]  # high
            fix_lows = [bar[3] for bar in fix_bars]   # low
            
        fix_high = max(fix_highs)
        fix_low = min(fix_lows)
        
        fix_result = {
            'left_i': left_bound,
            'right_i': right_bound,
            'top_price': fix_high,
            'bot_price': fix_low,
            'center_candle_index': candle_index,
            'center_price': center_price,
            'range_pct': (fix_high - fix_low) / center_price,
            'method': 'green_highlight'
        }
        
        print(f"[AI DEBUG] FIX from highlight: left={left_bound}, right={right_bound}, range={fix_high:.2f}-{fix_low:.2f}")
        
        return fix_result
        
    except Exception as e:
        print(f"[AI ERROR] Failed to build FIX from green highlight: {e}")
        return None


def _detect_ray_from_fix(bars: List[Dict[str, Any]], fix_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Detect RAY - ЛОЙ-ФИКС согласно базе знаний.
    
    ЛОЙ-ФИКС = самый низкий LOW между областью FIX и HI-pattern
    RAY = горизонтальная линия от этого лоя
    """
    if not fix_info:
        return None
    
    fix_end = fix_info['right_i']
    if fix_end >= len(bars) - 5:
        return None
    
    # По базе: ищем ЛОЙ-ФИКС между FIX и HI-pattern
    # HI-pattern = самый высокий пик после FIX 
    
    # Сначала находим HI-pattern (самый высокий пик после FIX)
    search_start = fix_end + 1  
    search_end = min(len(bars), len(bars) - 5)  # До конца данных
    
    hi_pattern_idx = None
    max_high = 0.0
    
    # Находим самый высокий пик после FIX 
    for i in range(search_start, search_end):
        bar = bars[i]
        bar_high = bar['high'] if isinstance(bar, dict) else bar[2]
        
        if bar_high > max_high:
            max_high = bar_high
            hi_pattern_idx = i
    
    if hi_pattern_idx is None:
        print("[AI DEBUG] No HI-pattern found after FIX")
        return None
        
    print(f"[AI DEBUG] Found HI-pattern at index {hi_pattern_idx}, high {max_high:.2f}")
    
    # Теперь ищем ЛОЙ-ФИКС = самый низкий LOW между FIX и HI-pattern
    loy_fix_idx = None
    min_low = float('inf')
    
    for i in range(fix_end + 1, hi_pattern_idx + 1):
        bar = bars[i]
        bar_low = bar['low'] if isinstance(bar, dict) else bar[3]
        
        if bar_low < min_low:
            min_low = bar_low
            loy_fix_idx = i
    
    if loy_fix_idx is None:
        print("[AI DEBUG] No LOY-FIX found between FIX and HI-pattern")
        return None
    
    print(f"[AI DEBUG] Found LOY-FIX at index {loy_fix_idx}, low {min_low:.2f}")
    
    # Ищем валидацию RAY - когда цена пройдет его сверху вниз после HI-pattern
    ray_validation_idx = loy_fix_idx  # По умолчанию заканчивается в точке лоя
    
    # Ищем валидацию после HI-pattern
    for i in range(hi_pattern_idx + 1, min(len(bars), hi_pattern_idx + 50)):
        bar = bars[i]
        bar_low = bar['low'] if isinstance(bar, dict) else bar[3]
        
        # Валидация = цена прошла уровень RAY сверху вниз на 1-2 тика
        if bar_low < min_low - min_low * 0.001:  # На 0.1% ниже уровня RAY
            ray_validation_idx = i
            print(f"[AI DEBUG] RAY validation at index {i}, price {bar_low:.2f}")
            break
    
    return {
        'from_i': loy_fix_idx,
        'to_i': ray_validation_idx, 
        'low_price': min_low,
        'hi_pattern_idx': hi_pattern_idx
    }


if __name__ == "__main__":
    # Simple test
    test_bars = [
        {'ts_open_ms': i*1000, 'open': 100+i, 'high': 105+i, 'low': 95+i, 'close': 102+i, 'volume': 1000}
        for i in range(50)
    ]
    test_meta = {'symbol': 'TEST', 'timeframe': '15m', 'datetime': '2025-01-01 12:00'}
    
    result = detect_short_pattern(test_bars, test_meta)
    print(f"Test result: {result}")
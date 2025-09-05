"""
Pattern Analyzer - координатор анализа FPF паттернов
Извлечен из tv_ingest_hybrid.py для разделения ответственности
"""
import sys
import pathlib
from datetime import datetime, timezone, timedelta
import pandas as pd

# Добавляем путь к проекту
_here = pathlib.Path(__file__).resolve()
_proj_root = _here.parent.parent
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))

# Импорты модулей
try:
    from ai.ocr_engine_new import SimpleOCREngine
    OCR_AVAILABLE = True
except Exception as e:
    OCR_AVAILABLE = False
    print(f"❌ OCR Engine failed: {e}")

try:
    from core.ai_search_pattern.fpf_detector_new import FpfPatternDetector, FpfPattern
    FPF_AVAILABLE = True
except Exception as e:
    FPF_AVAILABLE = False
    print(f"❌ FPF Detector failed: {e}")

try:
    from sync.simple_data_loader import load_data_for_analysis
    DATA_LOADER_AVAILABLE = True  
except Exception as e:
    DATA_LOADER_AVAILABLE = False
    print(f"❌ Data loader failed: {e}")


class PatternAnalyzer:
    """Координатор анализа FPF паттернов"""
    
    def __init__(self):
        # Инициализация движков
        self.ocr_engine = SimpleOCREngine() if OCR_AVAILABLE else None
        self.fpf_detector = FpfPatternDetector() if FPF_AVAILABLE else None
        
        # Текущее состояние
        self.current_data = None
        self.current_pattern = None
        
        # Коллбеки для UI обновлений
        self.on_status_update = None
        self.on_chart_draw = None
        self.on_pattern_found = None
        
    def analyze_image(self, image_path):
        """Полный анализ изображения TradingView"""
        if not self.ocr_engine:
            raise Exception("OCR engine not available")
            
        if not self.fpf_detector:
            raise Exception("FPF detector not available")
            
        try:
            # 1. OCR распознавание
            self._update_status("🔍 Analyzing screenshot with OCR...")
            ocr_result = self.ocr_engine.extract_chart_info(image_path)
            
            if not ocr_result:
                raise Exception("Failed to extract trading info from screenshot")
            
            print(f"[OCR] Parsed result: {ocr_result}")
            
            # 2. Загрузка данных
            symbol = ocr_result.get('symbol', 'BTCUSDT')
            timeframe = ocr_result.get('timeframe', '15m')
            datetime_str = ocr_result.get('datetime')
            
            if not datetime_str:
                raise Exception("Could not extract datetime from screenshot")
                
            self._update_status(f"📊 Loading data for {symbol} {timeframe}...")
            
            # Загружаем данные
            target_datetime = datetime.fromisoformat(datetime_str)
            print(f"Loading data for {symbol} {timeframe} around {target_datetime}")
            
            if DATA_LOADER_AVAILABLE:
                self.current_data = load_data_for_analysis(
                    symbol=symbol,
                    timeframe=timeframe, 
                    target_dt=target_datetime
                )
            else:
                raise Exception("Data loader not available")
            
            if self.current_data is None or self.current_data.empty:
                raise Exception(f"No data loaded for {symbol} {timeframe}")
                
            print(f"✅ Loaded {len(self.current_data)} candles")
            
            # 3. Поиск OCR свечи
            ocr_candle_idx = self._find_ocr_candle_index(target_datetime)
            
            if ocr_candle_idx is None:
                raise Exception("Could not find OCR candle in loaded data")
                
            print(f"🎯 OCR candle index: {ocr_candle_idx} (из {len(self.current_data)} свечей)")
            
            # 4. Отрисовка графика
            self._update_status("🎨 Drawing chart...")
            if self.on_chart_draw:
                self.on_chart_draw(self.current_data)
            
            # 5. Анализ паттерна
            self._update_status("🔍 Detecting FPF pattern...")
            
            # Конвертируем в формат для детектора
            candlesticks = self._convert_to_candlesticks(self.current_data)
            
            # Запускаем детекцию
            pattern_result = self.fpf_detector.detect_pattern(
                candlesticks, ocr_candle_idx
            )
            
            if pattern_result:
                self.current_pattern = pattern_result
                confidence = getattr(pattern_result, 'confidence', 0.0)
                self._update_status(f"✅ FPF Pattern detected with confidence {confidence:.2f}")
                
                # Уведомляем UI о найденном паттерне
                if self.on_pattern_found:
                    self.on_pattern_found(pattern_result, candlesticks, ocr_candle_idx)
            else:
                self._update_status("❌ No FPF pattern detected")
                # Пытаемся нарисовать частичные результаты
                self._try_partial_analysis(candlesticks, ocr_candle_idx)
                
        except Exception as e:
            error_msg = f"❌ Analysis failed: {e}"
            self._update_status(error_msg)
            raise
            
    def _find_ocr_candle_index(self, target_datetime):
        """Поиск индекса свечи по времени из OCR"""
        if self.current_data is None:
            return None
            
        target_ts = target_datetime.timestamp() * 1000  # в миллисекундах
        
        # Ищем ближайшую свечу по времени
        min_diff = float('inf')
        best_idx = None
        
        for idx, row in self.current_data.iterrows():
            candle_ts = row['timestamp']
            diff = abs(candle_ts - target_ts)
            
            if diff < min_diff:
                min_diff = diff
                best_idx = idx
                
        return best_idx
        
    def _convert_to_candlesticks(self, data):
        """Конвертирует DataFrame в формат для детектора"""
        candlesticks = []
        
        for _, row in data.iterrows():
            # Создаем объект свечи
            class CandleData:
                def __init__(self, open_val, high, low, close):
                    self.open = open_val
                    self.high = high
                    self.low = low
                    self.close = close
            
            candle = CandleData(
                row['open'],
                row['high'], 
                row['low'],
                row['close']
            )
            candlesticks.append(candle)
            
        return candlesticks
        
    def _try_partial_analysis(self, candlesticks, ocr_candle_idx):
        """Пытается найти частичные результаты для отображения"""
        try:
            # Пытаемся найти FIX область
            fix_area = self.fpf_detector._find_plateau_around_ocr(candlesticks, ocr_candle_idx)
            
            if fix_area:
                print(f"✅ Found FIX area: {fix_area}")
                
                # Пытаемся найти LOY-FIX
                loy_fix = self.fpf_detector._find_loy_fix(candlesticks, fix_area)
                if loy_fix:
                    print(f"✅ Found LOY-FIX: {loy_fix}")
                    
                    # Пытаемся найти HI-PATTERN
                    hi_pattern = self.fpf_detector._find_hi_pattern(candlesticks, fix_area, loy_fix)
                    if hi_pattern:
                        print(f"✅ Found HI-PATTERN: {hi_pattern}")
                
                # Уведомляем UI о частичных результатах
                if self.on_pattern_found:
                    partial_pattern = type('PartialPattern', (), {
                        'fix_area': fix_area,
                        'loy_fix': loy_fix if 'loy_fix' in locals() else None,
                        'hi_pattern': hi_pattern if 'hi_pattern' in locals() else None,
                        'is_complete': False
                    })()
                    
                    self.on_pattern_found(partial_pattern, candlesticks, ocr_candle_idx)
                    
        except Exception as e:
            print(f"Partial analysis failed: {e}")
            
    def _update_status(self, message):
        """Обновляет статус через коллбек"""
        if self.on_status_update:
            self.on_status_update(message)
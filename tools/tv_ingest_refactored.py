"""
TV Ingest Refactored - модульная версия анализатора FPF паттернов
Заменяет старый tv_ingest_hybrid.py, теперь использует разделенные модули
"""
import sys
import pathlib

# Добавляем путь к проекту
_here = pathlib.Path(__file__).resolve()
_proj_root = _here.parent.parent
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))

# Импорт наших модулей
from ui.tv_ingest_window import TVIngestWindow
from ui.pattern_analyzer import PatternAnalyzer  
from visualization.pattern_drawer import FPFPatternDrawer
from visualization.chart_renderer import ChartRenderer


class TVIngestApp:
    """Главное приложение TV Ingest с модульной архитектурой"""
    
    def __init__(self):
        print("🚀 Starting Refactored FPF Bot...")
        
        # Создаем компоненты
        self.window = TVIngestWindow()
        self.analyzer = PatternAnalyzer()
        self.pattern_drawer = FPFPatternDrawer(self.window.canvas)
        self.chart_renderer = ChartRenderer(self.window.canvas)
        
        # Связываем коллбеки (паттерн Observer)
        self._setup_callbacks()
        
        print("✅ Refactored TV Ingest initialized")
        
    def _setup_callbacks(self):
        """Настройка связей между компонентами"""
        # UI -> Analyzer (разделяем загрузку и анализ)
        self.window.on_image_loaded = self._on_image_loaded
        self.window.on_pattern_analyze = self._manual_analyze
        
        # Analyzer -> UI
        self.analyzer.on_status_update = self.window.status
        self.analyzer.on_chart_draw = self._on_chart_draw
        self.analyzer.on_pattern_found = self._on_pattern_found
        
    def _on_image_loaded(self, image_path):
        """Обработка загрузки изображения (без автоматического анализа)"""
        self.window.status(f"📷 Image loaded. Click 'Analyze FPF' to start.")
        
    def _manual_analyze(self):
        """Ручной запуск анализа"""
        if self.window.current_image_path:
            self.analyzer.analyze_image(self.window.current_image_path)
        else:
            self.window.status("❌ No image loaded")
            
    def _on_chart_draw(self, data):
        """Отрисовка графика"""
        self.chart_renderer.draw_chart(data)
        
    def _on_pattern_found(self, pattern, candlesticks, ocr_candle_idx):
        """Обработка найденного паттерна"""
        # Очищаем предыдущий паттерн
        self.pattern_drawer.clear_pattern()
        
        # Рисуем найденные элементы
        if hasattr(pattern, 'fix_area') and pattern.fix_area:
            self.pattern_drawer.draw_fix_area(pattern.fix_area, candlesticks)
            
        if hasattr(pattern, 'loy_fix') and pattern.loy_fix:
            self.pattern_drawer.draw_loy_fix(pattern.loy_fix, candlesticks)
            
        if hasattr(pattern, 'hi_pattern') and pattern.hi_pattern:
            self.pattern_drawer.draw_hi_pattern(pattern.hi_pattern, candlesticks)
            
        # Рисуем RAY если паттерн полный
        if getattr(pattern, 'is_complete', True):
            if hasattr(pattern, 'loy_fix') and hasattr(pattern, 'hi_pattern'):
                # Проверяем валидацию RAY
                ray_validated_at = self._check_ray_validation(
                    pattern.loy_fix, pattern.hi_pattern, candlesticks
                )
                self.pattern_drawer.draw_ray(
                    pattern.loy_fix, pattern.hi_pattern, candlesticks, ray_validated_at
                )
                
        # Подсвечиваем OCR свечу
        if ocr_candle_idx is not None:
            self.chart_renderer.highlight_candle(ocr_candle_idx, self.analyzer.current_data)
            
        self.window.status("✅ Pattern visualization complete")
        
    def _check_ray_validation(self, loy_fix, hi_pattern, candlesticks):
        """Проверка валидации RAY"""
        if not loy_fix or not hi_pattern:
            return None
            
        loy_idx, loy_price = loy_fix
        hi_idx, hi_price = hi_pattern
        
        # Ищем где цена после HI-PATTERN пробила RAY уровень вниз
        for i in range(hi_idx + 1, min(len(candlesticks), hi_idx + 50)):
            candle_low = candlesticks[i].low
            if candle_low < (loy_price - 0.02):  # пробили на 2 тика вниз
                print(f"RAY validation: candle {i} broke below {loy_price:.2f} at {candle_low:.2f}")
                return i
                
        return None
        
    def run(self):
        """Запуск приложения"""
        self.window.mainloop()


def main():
    """Точка входа"""
    app = TVIngestApp()
    app.run()


if __name__ == "__main__":
    main()
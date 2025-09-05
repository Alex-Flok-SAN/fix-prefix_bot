"""
Snapp - быстрый анализатор FPF паттернов из скриншотов TradingView
Just snap, analyze, trade! 📸
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


class FPFSnapApp:
    """FPF Snap - быстрый анализатор паттернов"""
    
    def __init__(self):
        print("📸 Starting FPF Snap...")
        
        # Создаем компоненты
        self.window = TVIngestWindow()
        self.analyzer = PatternAnalyzer()
        self.pattern_drawer = FPFPatternDrawer(self.window.canvas)
        self.chart_renderer = ChartRenderer(self.window.canvas)
        
        # Связываем коллбеки (паттерн Observer)
        self._setup_callbacks()
        
        print("✅ FPF Snap ready for pattern analysis")
        
    def _setup_callbacks(self):
        """Настройка связей между компонентами"""
        # UI -> Analyzer (разделяем загрузку и анализ)
        self.window.on_image_loaded = self._on_image_loaded
        self.window.on_pattern_analyze = self._manual_analyze
        self.window.on_canvas_resize = self._on_canvas_resize
        self.window.on_fix_area_changed = self._on_fix_area_changed
        self.window.on_take_profit_area_changed = self._on_take_profit_area_changed
        
        # Analyzer -> UI
        self.analyzer.on_status_update = self.window.status
        self.analyzer.on_chart_draw = self._on_chart_draw
        self.analyzer.on_pattern_found = self._on_pattern_found
        
    def _on_image_loaded(self, image_path):
        """Обработка загрузки изображения с автоматическим анализом"""
        self.window.status("📷 Image loaded, starting automatic analysis...")
        # Автоматически запускаем анализ
        self.analyzer.analyze_image(image_path)
        
    def _manual_analyze(self):
        """Ручной запуск анализа"""
        if self.window.current_image_path:
            self.analyzer.analyze_image(self.window.current_image_path)
        else:
            self.window.status("❌ No image loaded")
            
    def _on_canvas_resize(self, event):
        """Обработка изменения размера canvas - обновление FPF паттернов"""
        # Если есть сохраненные данные графика, перерисовываем его
        if hasattr(self.chart_renderer, 'current_data') and self.chart_renderer.current_data is not None:
            # Сохраняем состояние PREFIX перед очисткой
            prefix_was_drawn = getattr(self, '_prefix_drawn', False)
            
            # ВАЖНО: Очищаем canvas перед перерисовкой, чтобы избежать артефактов
            self.window.canvas.delete("all")
            # Также очищаем внутренние списки элементов
            self.pattern_drawer.clear_pattern()
            
            # Восстанавливаем состояние PREFIX
            self._prefix_drawn = prefix_was_drawn
            
            # Перерисовываем график с паттерном
            self.chart_renderer.draw_chart(self.chart_renderer.current_data)
            
            # Если есть сохраненный паттерн, перерисовываем его
            if hasattr(self, '_last_pattern') and self._last_pattern:
                self._draw_fpf_pattern(self._last_pattern, self._last_candlesticks)
        
    def _on_chart_draw(self, data):
        """Отрисовка графика"""
        self.chart_renderer.draw_chart(data)
        
    def _on_pattern_found(self, pattern, candlesticks, ocr_candle_idx):
        """Обработка найденного паттерна"""
        # Сохраняем паттерн для перерисовки при изменении размера
        self._last_pattern = pattern
        self._last_candlesticks = candlesticks
        # Сбрасываем флаги при новом паттерне
        self._prefix_drawn = False
        self._take_profit_drawn = False
        
        # Очищаем предыдущий паттерн
        self.pattern_drawer.clear_pattern()
        
        # Рисуем новый паттерн
        self._draw_fpf_pattern(pattern, candlesticks)
        
    def _draw_fpf_pattern(self, pattern, candlesticks):
        """Отрисовка элементов FPF паттерна"""
        
        # Рисуем найденные элементы
        fix_area = None
        if hasattr(pattern, 'fix_area') and pattern.fix_area:
            fix_area = pattern.fix_area
            self.pattern_drawer.draw_fix_area(pattern.fix_area, candlesticks)
        elif hasattr(pattern, 'fix_start_idx') and hasattr(pattern, 'fix_end_idx'):
            # Альтернативный способ получения FIX области из FpfPattern
            fix_area = (pattern.fix_start_idx, pattern.fix_end_idx, pattern.fix_low, pattern.fix_high)
            self.pattern_drawer.draw_fix_area(fix_area, candlesticks)
            
        # Детектируем и рисуем TAKE PROFIT область (флэт перед FIX)
        if fix_area:
            take_profit_area = self.pattern_drawer.detect_take_profit_area(candlesticks, fix_area)
            if take_profit_area:
                self.pattern_drawer.draw_take_profit_area(take_profit_area, candlesticks)
                self._last_take_profit_area = take_profit_area  # сохраняем для связывания
                self._take_profit_drawn = True
                print(f"✅ TAKE PROFIT область добавлена к паттерну")
            
        if hasattr(pattern, 'loy_fix') and pattern.loy_fix:
            self.pattern_drawer.draw_loy_fix(pattern.loy_fix, candlesticks)
        elif hasattr(pattern, 'loy_fix_idx') and hasattr(pattern, 'loy_fix_price'):
            # Из FpfPattern объекта
            loy_fix = (pattern.loy_fix_idx, pattern.loy_fix_price)
            self.pattern_drawer.draw_loy_fix(loy_fix, candlesticks)
            
        if hasattr(pattern, 'hi_pattern') and pattern.hi_pattern:
            self.pattern_drawer.draw_hi_pattern(pattern.hi_pattern, candlesticks)
        elif hasattr(pattern, 'hi_pattern_idx') and hasattr(pattern, 'hi_pattern_price'):
            # Из FpfPattern объекта
            hi_pattern = (pattern.hi_pattern_idx, pattern.hi_pattern_price)
            self.pattern_drawer.draw_hi_pattern(hi_pattern, candlesticks)
            
        # Рисуем RAY ТОЛЬКО если цена пошла вниз от HI-PATTERN (по базе знаний)
        if getattr(pattern, 'is_complete', True):
            if hasattr(pattern, 'loy_fix_idx') and hasattr(pattern, 'hi_pattern_idx'):
                # Формируем данные в правильном формате для draw_ray
                loy_fix = (pattern.loy_fix_idx, pattern.loy_fix_price)
                hi_pattern = (pattern.hi_pattern_idx, pattern.hi_pattern_price)
                
                # ПРОВЕРКА ПО БАЗЕ: RAY рисуется только когда "цена от Hi-pattern пошла вниз"
                price_went_down = self._check_price_went_down_from_hi_pattern(
                    hi_pattern, candlesticks
                )
                
                if price_went_down:
                    print(f"✅ Цена пошла вниз от HI-PATTERN - рисуем RAY")
                    # Проверяем валидацию RAY
                    ray_validated_at = self._check_ray_validation(
                        loy_fix, hi_pattern, candlesticks
                    )
                    print(f"🔍 RAY: loy_fix={loy_fix}, hi_pattern={hi_pattern}")
                    self.pattern_drawer.draw_ray(
                        loy_fix, hi_pattern, candlesticks, ray_validated_at
                    )
                    print("✅ RAY нарисован")
                    
                    # Проверяем - если RAY валидирован, рисуем PREFIX (включая при перерисовке)
                    if ray_validated_at is not None and (not hasattr(self, '_prefix_drawn') or not getattr(self.pattern_drawer, '_prefix_items', [])):
                        # Получаем FIX область для расчета PREFIX  
                        fix_area = None
                        if hasattr(pattern, 'fix_area') and pattern.fix_area:
                            fix_area = pattern.fix_area
                        elif hasattr(pattern, 'fix_start_idx') and hasattr(pattern, 'fix_end_idx'):
                            fix_area = (pattern.fix_start_idx, pattern.fix_end_idx, pattern.fix_low, pattern.fix_high)
                        
                        if fix_area:
                            ray_level = pattern.loy_fix_price  # уровень RAY = LOY-FIX цена
                            self.pattern_drawer.draw_prefix_area(fix_area, ray_level, candlesticks, ray_validated_at)
                            print(f"✅ PREFIX область появилась ПОСЛЕ валидации RAY на индексе {ray_validated_at}")
                            self._prefix_drawn = True  # флаг что PREFIX уже нарисован
                            self._ray_validated_at = ray_validated_at  # сохраняем для обновлений
                else:
                    print(f"⏳ Цена еще не пошла вниз от HI-PATTERN - RAY не рисуем")
            else:
                print(f"❌ RAY не нарисован - pattern attributes: {dir(pattern)}")
                
        # Убрали подсветку OCR свечи - не нужна
            
        self.window.status("✅ Pattern visualization complete")
    
    def _on_fix_area_changed(self, fix_coords):
        """Обработка изменения FIX области - обновляем PREFIX"""
        print(f"🔄 FIX область изменена: {fix_coords}")
        
        # Если паттерн найден и PREFIX должен быть отображен
        if hasattr(self, '_last_pattern') and self._last_pattern and hasattr(self, '_prefix_drawn') and self._prefix_drawn:
            print("🔄 Обновляем PREFIX область согласно новой FIX")
            
            # Пересчитываем PREFIX с новыми координатами FIX
            self._update_prefix_from_canvas_coords(fix_coords)
            
            # Также обновляем связанную TAKE PROFIT область если она существует
            if hasattr(self, '_take_profit_drawn') and self._take_profit_drawn:
                self._update_take_profit_relative_to_fix(fix_coords)
    
    def _update_prefix_from_canvas_coords(self, fix_coords):
        """Обновляет PREFIX область на основе новых canvas координат FIX"""
        if not hasattr(self, '_last_candlesticks') or not self._last_candlesticks:
            return
            
        # Конвертируем canvas координаты обратно в ценовые
        pattern = self._last_pattern
        candlesticks = self._last_candlesticks
        
        # Получаем canvas размеры для конверсии
        canvas_width, canvas_height = self.window.get_canvas_size()
        
        # Конвертируем canvas Y координаты в цены
        canvas_left, canvas_top, canvas_right, canvas_bottom = fix_coords['canvas']
        
        # Примерный алгоритм конвертации (нужно синхронизировать с chart_renderer)
        margin_left = 50  # из chart_renderer
        margin_top = 30
        chart_width = canvas_width - margin_left - 10
        chart_height = canvas_height - margin_top - 50
        
        # Найдем min/max цены для scale
        all_prices = []
        for candle in candlesticks:
            all_prices.extend([candle.high, candle.low])
        min_price = min(all_prices)
        max_price = max(all_prices)
        price_range = max_price - min_price
        
        if price_range == 0:
            price_range = max_price * 0.01
            
        # Конвертируем Y координаты обратно в цены
        new_fix_high = max_price - (canvas_top - margin_top) * price_range / chart_height
        new_fix_low = max_price - (canvas_bottom - margin_top) * price_range / chart_height
        
        print(f"🔄 Новые цены FIX: {new_fix_low:.2f} - {new_fix_high:.2f}")
        
        # Обновляем pattern объект
        if hasattr(pattern, 'fix_high') and hasattr(pattern, 'fix_low'):
            pattern.fix_high = new_fix_high
            pattern.fix_low = new_fix_low
        
        # Очищаем старую PREFIX область
        if hasattr(self.pattern_drawer, '_prefix_items'):
            for item in self.pattern_drawer._prefix_items:
                self.window.canvas.delete(item)
            self.pattern_drawer._prefix_items.clear()
        
        # Перерисовываем PREFIX с новыми координатами
        if hasattr(pattern, 'loy_fix_price') and hasattr(self, '_ray_validated_at'):
            fix_area = (pattern.fix_start_idx, pattern.fix_end_idx, new_fix_low, new_fix_high)
            ray_level = pattern.loy_fix_price
            self.pattern_drawer.draw_prefix_area(fix_area, ray_level, candlesticks, self._ray_validated_at)
            print("✅ PREFIX область обновлена согласно новой FIX области")
            
    def _on_take_profit_area_changed(self, tp_coords):
        """Обработка изменения TAKE PROFIT области - обновляем связи"""
        print(f"🔄 TAKE PROFIT область изменена: {tp_coords}")
        
        # Сохраняем новые координаты TAKE PROFIT
        if hasattr(self, '_last_take_profit_area'):
            # Обновляем сохраненные координаты на основе canvas изменений
            self._update_take_profit_from_canvas_coords(tp_coords)
            
    def _update_take_profit_relative_to_fix(self, fix_coords):
        """Обновляет TAKE PROFIT область при изменении FIX (автоматическая связь)"""
        if not hasattr(self, '_last_take_profit_area') or not hasattr(self, '_last_candlesticks'):
            return
            
        # В данной реализации TAKE PROFIT остается независимым от FIX
        # Но можно добавить логику для пропорционального изменения
        print("🔗 TAKE PROFIT область остается независимой от изменений FIX")
        
    def _update_take_profit_from_canvas_coords(self, tp_coords):
        """Обновляет TAKE PROFIT область на основе новых canvas координат"""
        if not hasattr(self, '_last_candlesticks') or not self._last_candlesticks:
            return
            
        candlesticks = self._last_candlesticks
        
        # Получаем canvas размеры для конверсии
        canvas_width, canvas_height = self.window.get_canvas_size()
        
        # Конвертируем canvas Y координаты в цены (аналогично PREFIX логике)
        canvas_left, canvas_top, canvas_right, canvas_bottom = tp_coords['canvas']
        
        margin_left = 50  # из chart_renderer
        margin_top = 30
        chart_width = canvas_width - margin_left - 10
        chart_height = canvas_height - margin_top - 50
        
        # Найдем min/max цены для scale
        all_prices = []
        for candle in candlesticks:
            all_prices.extend([candle.high, candle.low])
        min_price = min(all_prices)
        max_price = max(all_prices)
        price_range = max_price - min_price
        
        if price_range == 0:
            price_range = max_price * 0.01
            
        # Конвертируем Y координаты обратно в цены
        new_tp_high = max_price - (canvas_top - margin_top) * price_range / chart_height
        new_tp_low = max_price - (canvas_bottom - margin_top) * price_range / chart_height
        
        print(f"🔄 Новые цены TAKE PROFIT: {new_tp_low:.2f} - {new_tp_high:.2f}")
        
        # Обновляем сохраненную область
        if hasattr(self, '_last_take_profit_area'):
            tp_start_idx, tp_end_idx = self._last_take_profit_area[0], self._last_take_profit_area[1]
            self._last_take_profit_area = (tp_start_idx, tp_end_idx, new_tp_low, new_tp_high)
            print("✅ TAKE PROFIT область обновлена")
        
    def _check_price_went_down_from_hi_pattern(self, hi_pattern, candlesticks):
        """
        Проверяет что цена пошла вниз от HI-PATTERN (по базе знаний)
        База: "Как только цена от Hi-pattern пошла вниз, рисуем RAY"
        """
        if not hi_pattern or not candlesticks:
            return False
            
        hi_idx, hi_price = hi_pattern
        
        # Проверяем есть ли свечи после HI-PATTERN
        if hi_idx >= len(candlesticks) - 1:
            return False
            
        # Ищем признаки движения вниз после HI-PATTERN
        # Достаточно 1-2 свечей с закрытием ниже HI-PATTERN
        down_moves = 0
        for i in range(hi_idx + 1, min(len(candlesticks), hi_idx + 5)):  # проверяем 4 свечи
            candle = candlesticks[i]
            
            # Если закрытие ниже HI-PATTERN цены - это движение вниз
            if candle.close < hi_price:
                down_moves += 1
                
            # Если хотя бы 2 свечи закрылись ниже - цена пошла вниз
            if down_moves >= 2:
                print(f"✅ Цена пошла вниз: свеча #{i} close={candle.close:.2f} < hi_price={hi_price:.2f}")
                return True
                
        print(f"⏳ Цена еще не пошла вниз от HI-PATTERN ({hi_price:.2f}), down_moves={down_moves}")
        return False

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
    app = FPFSnapApp()
    app.run()


if __name__ == "__main__":
    main()
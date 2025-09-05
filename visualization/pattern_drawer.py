"""
FPF Pattern Drawer - >B@8A>2:0 M;5<5=B>2 ?0BB5@=0 =0 canvas
72;5G5= 87 tv_ingest_hybrid.py 4;O <>4C;L=>AB8
"""
import tkinter as tk
import sys
import pathlib

# >102;O5< ?CBL : ?@>5:BC
_here = pathlib.Path(__file__).resolve()
_proj_root = _here.parent.parent
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))


class FPFPatternDrawer:
    """B@8A>2:0 FPF ?0BB5@=>2 =0 canvas"""
    
    def __init__(self, canvas):
        self.canvas = canvas
        
        # -;5<5=BK 287C0;870F88 
        self._fix_items = []
        self._ray_items = []
        self._hi_pattern_items = []
        self._loy_fix_items = []
        self._take_profit_items = []
        
        # 0@0<5B@K >B@8A>2:8
        self.margin_left = 60
        self.margin_right = 20
        self.margin_top = 20
        self.margin_bottom = 60
        
    def clear_pattern(self):
        """G8AB:0 FPF ?0BB5@=0 A 3@0D8:0"""
        for items in [self._fix_items, self._ray_items, 
                     self._hi_pattern_items, self._loy_fix_items, self._take_profit_items]:
            for item in items:
                self.canvas.delete(item)
            items.clear()
            
    def draw_fix_area(self, fix_area, candle_data):
        """ 8AC5B FIX >1;0ABL (?;0B> :>=A>;840F88)"""
        if not fix_area or not candle_data:
            return
            
        # >;CG05< :>>@48=0BK
        start_idx, end_idx, low_price, high_price = fix_area[:4]
        
        # KG8A;O5< ?>78F88
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        data_len = len(candle_data)
        
        # Доступная область для графика (как в ChartRenderer)
        chart_width = canvas_width - self.margin_left - self.margin_right
        chart_height = canvas_height - self.margin_top - self.margin_bottom
        
        # ТОЧНО ТАКИЕ ЖЕ ФУНКЦИИ КАК В ChartRenderer
        def idx_to_x(idx):
            # Добавляем 0.5 для центрирования свечи (как в ChartRenderer)
            return self.margin_left + ((idx + 0.5) * chart_width / data_len)
            
        def price_to_y(price):
            # ВАЖНО: используем min/max от candle_data точно как в ChartRenderer
            if hasattr(candle_data[0], 'high'):
                # Если это объекты свечей
                highs = [c.high for c in candle_data]
                lows = [c.low for c in candle_data]
            else:
                # Если это DataFrame
                highs = candle_data['high'].values if hasattr(candle_data, 'high') else [c.high for c in candle_data]
                lows = candle_data['low'].values if hasattr(candle_data, 'low') else [c.low for c in candle_data]
                
            min_price = float(min(lows))
            max_price = float(max(highs))
            price_range = max_price - min_price
            if price_range == 0:
                price_range = max_price * 0.01
            return self.margin_top + (max_price - price) * chart_height / price_range
        
        # >>@48=0BK ?@O<>C3>;L=8:0
        # КООРДИНАТЫ ПРЯМОУГОЛЬНИКА (С центрированием как в ChartRenderer)
        fix_left = self.margin_left + (start_idx + 0.5) * chart_width / data_len
        fix_right = self.margin_left + (end_idx + 0.5) * chart_width / data_len
        fix_top = price_to_y(high_price)
        fix_bottom = price_to_y(low_price)
        
        # Рисуем FIX прямоугольник (только контур, без заливки) с тегом для перетаскивания
        fix_rect = self.canvas.create_rectangle(
            fix_left, fix_top, fix_right, fix_bottom,
            outline="#A56BFF", width=3, fill="", tags="fix_area"
        )
        self._fix_items.append(fix_rect)
        
        # >102;O5< 8=B5@0:B82=K5 C3>;:8
        # УБИРАЕМ ИНТЕРАКТИВНЫЕ ЯКОРЯ - они отделяются от FIX при масштабировании
        self._add_fix_handles(fix_left, fix_top, fix_right, fix_bottom)
        
        # 5B:0 FIX
        fix_label = self.canvas.create_text(
            fix_left - 30, fix_top,
            text="FIX", fill="#A56BFF", font=("Arial", 12, "bold"), tags="fix_area"
        )
        self._fix_items.append(fix_label)
        
    def _add_fix_handles(self, left, top, right, bottom):
        """>102;O5B 8=B5@0:B82=K5 C3>;:8 4;O FIX >1;0AB8"""
        handle_size = 4
        
        # '5BK@5 C3;0
        handles = [
            (left, top),      # top-left
            (right, top),     # top-right  
            (left, bottom),   # bottom-left
            (right, bottom)   # bottom-right
        ]
        
        for x, y in handles:
            handle = self.canvas.create_rectangle(
                x - handle_size, y - handle_size,
                x + handle_size, y + handle_size,
                fill="#A56BFF", outline="white", width=1, tags="fix_handle"
            )
            self._fix_items.append(handle)
            
    def draw_loy_fix(self, loy_fix, candle_data):
        """ 8AC5B LOY-FIX B>G:C"""
        if not loy_fix or not candle_data:
            return
            
        loy_idx, loy_price = loy_fix
        data_len = len(candle_data)
        
        # Доступная область для графика
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        chart_width = canvas_width - self.margin_left - self.margin_right
        chart_height = canvas_height - self.margin_top - self.margin_bottom
        
        # $C=:F88 :>>@48=0B
        def idx_to_x(idx):
            return self.margin_left + (idx + 0.5) * chart_width / data_len
            
        def price_to_y(price):
            # Используем глобальные min/max цены для всех свечей (как в ChartRenderer)
            highs = [c.high for c in candle_data]
            lows = [c.low for c in candle_data]
            min_price = float(min(lows))
            max_price = float(max(highs))
            price_range = max_price - min_price
            if price_range == 0:
                price_range = max_price * 0.01
            return self.margin_top + (max_price - price) * chart_height / price_range
        
        # >>@48=0BK B>G:8
        loy_x = idx_to_x(loy_idx)
        loy_y = price_to_y(loy_price)
        
        #  8AC5< LOY-FIX B>G:C (:@0A=0O, меньшего размера)
        loy_point = self.canvas.create_oval(
            loy_x - 3, loy_y - 3, loy_x + 3, loy_y + 3,
            fill="#FF4444", outline="white", width=1
        )
        self._loy_fix_items.append(loy_point)
        
        # 5B:0 LOY-FIX (2=87C B>G:8)
        loy_label = self.canvas.create_text(
            loy_x, loy_y + 20,
            text="LOY-FIX", fill="#FF4444", font=("Arial", 10, "bold")
        )
        self._loy_fix_items.append(loy_label)
        
    def draw_hi_pattern(self, hi_pattern, candle_data):
        """ 8AC5B HI-PATTERN B>G:C"""
        if not hi_pattern or not candle_data:
            return
            
        hi_idx, hi_price = hi_pattern
        data_len = len(candle_data)
        
        # Доступная область для графика
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        chart_width = canvas_width - self.margin_left - self.margin_right
        chart_height = canvas_height - self.margin_top - self.margin_bottom
        
        # $C=:F88 :>>@48=0B
        def idx_to_x(idx):
            return self.margin_left + (idx + 0.5) * chart_width / data_len
            
        def price_to_y(price):
            # Используем глобальные min/max цены для всех свечей (как в ChartRenderer)
            highs = [c.high for c in candle_data]
            lows = [c.low for c in candle_data]
            min_price = float(min(lows))
            max_price = float(max(highs))
            price_range = max_price - min_price
            if price_range == 0:
                price_range = max_price * 0.01
            return self.margin_top + (max_price - price) * chart_height / price_range
        
        # >>@48=0BK B>G:8
        hi_x = idx_to_x(hi_idx)
        hi_y = price_to_y(hi_price)
        
        #  8AC5< HI-PATTERN B>G:C (A8=OO)
        hi_point = self.canvas.create_oval(
            hi_x - 6, hi_y - 6, hi_x + 6, hi_y + 6,
            fill="#44FF44", outline="white", width=2
        )
        self._hi_pattern_items.append(hi_point)
        
        # 5B:0 HI-PATTERN
        hi_label = self.canvas.create_text(
            hi_x, hi_y - 20,
            text="HI-PATTERN", fill="#44FF44", font=("Arial", 10, "bold")
        )
        self._hi_pattern_items.append(hi_label)
        
    def draw_ray(self, loy_fix, hi_pattern, candle_data, ray_validated_at=None):
        """Рисует RAY - горизонтальную линию валидации от LOY-FIX"""
        print(f"🎯 draw_ray вызван: loy_fix={loy_fix}, candle_data_len={len(candle_data) if candle_data else 0}")
        if not loy_fix or not candle_data:
            print("❌ RAY не нарисован - нет данных")
            return
            
        loy_idx, loy_price = loy_fix
        data_len = len(candle_data)
        
        # ИСПОЛЬЗУЕМ ТОЧНО ТАКИЕ ЖЕ КООРДИНАТЫ КАК В ChartRenderer
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        chart_width = canvas_width - self.margin_left - self.margin_right
        chart_height = canvas_height - self.margin_top - self.margin_bottom
        
        # ТОЧНО ТАКИЕ ЖЕ ФУНКЦИИ КАК В ChartRenderer
        def idx_to_x(idx):
            # Добавляем 0.5 для центрирования свечи (как в ChartRenderer)
            return self.margin_left + ((idx + 0.5) * chart_width / data_len)
            
        def price_to_y(price):
            # ВАЖНО: используем min/max от candle_data точно как в ChartRenderer
            if hasattr(candle_data[0], 'high'):
                # Если это объекты свечей
                highs = [c.high for c in candle_data]
                lows = [c.low for c in candle_data]
            else:
                # Если это DataFrame
                highs = candle_data['high'].values if hasattr(candle_data, 'high') else [c.high for c in candle_data]
                lows = candle_data['low'].values if hasattr(candle_data, 'low') else [c.low for c in candle_data]
                
            min_price = float(min(lows))
            max_price = float(max(highs))
            price_range = max_price - min_price
            if price_range == 0:
                price_range = max_price * 0.01
            return self.margin_top + (max_price - price) * chart_height / price_range
        
        # 0G0;L=0O B>G:0 RAY
        ray_start_x = idx_to_x(loy_idx)
        ray_y = price_to_y(loy_price)
        
        # Находим первый брейк RAY (2+ тика вниз от LOY-FIX уровня)
        ray_break_idx = None
        tick_size = 0.01  # Примерный размер тика для большинства инструментов
        break_threshold = loy_price - (2 * tick_size)  # 2 тика вниз от LOY-FIX
        
        # Ищем первую свечу после LOY-FIX, которая пробивает уровень на 2+ тика
        for i in range(loy_idx + 1, len(candle_data)):
            candle = candle_data[i]
            if candle.low <= break_threshold:
                ray_break_idx = i
                break
        
        # >=5G=0O B>G:0 RAY
        if ray_break_idx is not None:
            ray_end_x = idx_to_x(ray_break_idx)
        elif ray_validated_at:
            ray_end_x = idx_to_x(ray_validated_at)
        else:
            # По умолчанию - до конца графика или максимум 20 свечей вперед
            default_end_idx = min(loy_idx + 20, len(candle_data) - 1)
            ray_end_x = idx_to_x(default_end_idx)
        
        print(f"🔥 RAY координаты: start=({ray_start_x}, {ray_y}), end=({ray_end_x}, {ray_y})")
        print(f"🔥 RAY break_idx={ray_break_idx}, loy_idx={loy_idx}, loy_price={loy_price}")
        
        # Рисуем RAY линию - стиль зависит от валидации паттерна (ТОНЬШЕ В 2 РАЗА)
        if ray_validated_at is not None:
            # ✅ ПАТТЕРН ВАЛИДИРОВАН - сплошная линия (было 4, стало 2)
            ray_line = self.canvas.create_line(
                ray_start_x, ray_y, ray_end_x, ray_y,
                fill="#FFD700", width=2, tags="ray_validated"
            )
            print(f"✅ RAY ВАЛИДИРОВАН - сплошная линия")
        else:
            # ⏳ Паттерн не валидирован - пунктирная линия (было 2, стало 1)
            ray_line = self.canvas.create_line(
                ray_start_x, ray_y, ray_end_x, ray_y,
                fill="#FFD700", width=1, dash=(8, 4), tags="ray_pending"
            )
            print(f"⏳ RAY ожидает валидации - пунктирная линия")
        self._ray_items.append(ray_line)
        print(f"✅ RAY линия создана: canvas_item={ray_line}")
        
        # 5B:0 RAY
        # Если RAY валидирован, добавляем маркер точки пробоя
        if ray_validated_at is not None:
            validation_x = idx_to_x(ray_validated_at)
            validation_circle = self.canvas.create_oval(
                validation_x - 4, ray_y - 4, validation_x + 4, ray_y + 4,
                fill="#FF0000", outline="#FFFFFF", width=2, tags="ray_validation_point"
            )
            self._ray_items.append(validation_circle)
            print(f"🔥 Маркер валидации RAY создан на индексе {ray_validated_at}")
        
        # Подпись RAY по центру луча, сверху - показывает статус валидации
        ray_center_x = (ray_start_x + ray_end_x) / 2  # центр луча
        ray_text = "RAY ✅" if ray_validated_at is not None else "RAY ⏳"
        ray_label = self.canvas.create_text(
            ray_center_x, ray_y - 15,  # над лучом на 15 пикселей
            text=ray_text, fill="#FFD700", font=("Arial", 8, "bold")
        )
        self._ray_items.append(ray_label)
        print(f"✅ RAY метка создана: canvas_item={ray_label}")
        
    def draw_prefix_area(self, fix_area, ray_level, candle_data, ray_validation_idx=None):
        """Рисует PREFIX область - целевую зону для входов"""
        if not fix_area or not candle_data or ray_level is None:
            return
            
        # Распаковываем параметры FIX области
        fix_start_idx, fix_end_idx, fix_low_price, fix_high_price = fix_area[:4]
        fix_height = fix_high_price - fix_low_price  # высота FIX области
        
        # PREFIX область НА УРОВНЕ FIX и равен по высоте FIX
        # Появляется ПОСЛЕ валидации паттерна как целевая зона ретеста
        prefix_high = fix_high_price  # верх PREFIX = верх FIX
        prefix_low = fix_low_price    # низ PREFIX = низ FIX
        
        # ИСПОЛЬЗУЕМ ТОЧНО ТАКИЕ ЖЕ КООРДИНАТЫ КАК В ChartRenderer
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        chart_width = canvas_width - self.margin_left - self.margin_right
        chart_height = canvas_height - self.margin_top - self.margin_bottom
        data_len = len(candle_data)
        
        def price_to_y(price):
            if hasattr(candle_data[0], 'high'):
                highs = [c.high for c in candle_data]
                lows = [c.low for c in candle_data]
            else:
                highs = candle_data['high'].values if hasattr(candle_data, 'high') else [c.high for c in candle_data]
                lows = candle_data['low'].values if hasattr(candle_data, 'low') else [c.low for c in candle_data]
                
            min_price = float(min(lows))
            max_price = float(max(highs))
            price_range = max_price - min_price
            if price_range == 0:
                price_range = max_price * 0.01
            return self.margin_top + (max_price - price) * chart_height / price_range
        
        # Координаты PREFIX области - появляется С МОМЕНТА валидации RAY
        # PREFIX начинается прямо с свечи валидации паттерна
        if ray_validation_idx is not None:
            prefix_start_idx = ray_validation_idx  # начинается с момента валидации
            
            # Ищем когда цена УВЕРЕННО выйдет из PREFIX вниз (конец PREFIX зоны)
            prefix_end_idx = data_len - 1  # по умолчанию до конца данных
            
            # Логика завершения PREFIX: ищем момент когда цена ОКОНЧАТЕЛЬНО ушла из зоны
            # PREFIX - это зона для шортовых входов, она активна пока есть возвраты в эту область
            consecutive_breaks = 0
            
            for i in range(prefix_start_idx + 1, min(data_len, prefix_start_idx + 100)):
                candle = candle_data[i]
                
                # Считаем consecutive breaks - свечи закрывшиеся ниже PREFIX
                if candle.close < fix_low_price:
                    consecutive_breaks += 1
                elif candle.high > fix_low_price:  
                    # Если цена вернулась в PREFIX - сбрасываем счетчик
                    consecutive_breaks = 0
                
                # PREFIX заканчивается когда 10 свечей подряд НЕ возвращались в зону
                if consecutive_breaks >= 10:
                    prefix_end_idx = i
                    print(f"🎯 PREFIX конец найден: свеча #{i} - 10 свечей подряд без возврата в PREFIX зону")
                    break
            
            prefix_width_candles = prefix_end_idx - prefix_start_idx
        else:
            # Fallback если нет точки валидации
            prefix_start_idx = data_len - 15
            prefix_width_candles = fix_end_idx - fix_start_idx  # ширина равна FIX
        
        # Убеждаемся что PREFIX не выходит за границы canvas
        if prefix_start_idx >= data_len:
            prefix_start_idx = data_len - 8  # отступаем назад если нужно
            prefix_width_candles = 4
            
        prefix_left = self.margin_left + (prefix_start_idx + 0.5) * chart_width / data_len
        prefix_right = self.margin_left + (prefix_start_idx + prefix_width_candles + 0.5) * chart_width / data_len
        
        prefix_top = price_to_y(prefix_high)
        prefix_bottom = price_to_y(prefix_low)
        
        # Рисуем PREFIX прямоугольник (только контур, прозрачный как FIX)
        prefix_rect = self.canvas.create_rectangle(
            prefix_left, prefix_top, prefix_right, prefix_bottom,
            outline="#00FF88", width=3, fill="", tags="prefix_area"
        )
        self._prefix_items = getattr(self, '_prefix_items', [])
        self._prefix_items.append(prefix_rect)
        
        # Метка PREFIX
        prefix_label = self.canvas.create_text(
            prefix_left - 35, prefix_top,
            text="PREFIX", fill="#00FF88", font=("Arial", 10, "bold"), tags="prefix_area"
        )
        self._prefix_items.append(prefix_label)
        
        print(f"✅ PREFIX область нарисована: {prefix_low:.2f}-{prefix_high:.2f}")
        
    def draw_take_profit_area(self, take_profit_area, candle_data):
        """Рисует TAKE PROFIT область - целевую зону для закрытия позиций (флэт перед FIX)"""
        if not take_profit_area or not candle_data:
            return
            
        # Распаковываем параметры TAKE PROFIT области
        tp_start_idx, tp_end_idx, tp_low_price, tp_high_price = take_profit_area[:4]
        
        # ИСПОЛЬЗУЕМ ТОЧНО ТАКИЕ ЖЕ КООРДИНАТЫ КАК В ChartRenderer
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        chart_width = canvas_width - self.margin_left - self.margin_right
        chart_height = canvas_height - self.margin_top - self.margin_bottom
        data_len = len(candle_data)
        
        def price_to_y(price):
            if hasattr(candle_data[0], 'high'):
                highs = [c.high for c in candle_data]
                lows = [c.low for c in candle_data]
            else:
                highs = candle_data['high'].values if hasattr(candle_data, 'high') else [c.high for c in candle_data]
                lows = candle_data['low'].values if hasattr(candle_data, 'low') else [c.low for c in candle_data]
                
            min_price = float(min(lows))
            max_price = float(max(highs))
            price_range = max_price - min_price
            if price_range == 0:
                price_range = max_price * 0.01
            return self.margin_top + (max_price - price) * chart_height / price_range
        
        # Координаты TAKE PROFIT области (две связанные зоны) 
        tp_left = self.margin_left + (tp_start_idx + 0.5) * chart_width / data_len
        tp_right = self.margin_left + (tp_end_idx + 0.5) * chart_width / data_len
        tp_top = price_to_y(tp_high_price)
        tp_bottom = price_to_y(tp_low_price)
        
        # Разделяем на две связанные области как предложено пользователем
        tp_middle = (tp_top + tp_bottom) / 2  # средняя линия
        tp_center_x = (tp_left + tp_right) / 2  # центр по горизонтали
        
        # Область 1: Верхняя часть TAKE PROFIT (более приоритетная)
        tp_rect_1 = self.canvas.create_rectangle(
            tp_left, tp_top, tp_right, tp_middle,
            outline="#FF8C00", width=2, fill="", tags="take_profit_area_1"
        )
        self._take_profit_items.append(tp_rect_1)
        
        # Область 2: Нижняя часть TAKE PROFIT (дополнительная)
        tp_rect_2 = self.canvas.create_rectangle(
            tp_left, tp_middle, tp_right, tp_bottom,
            outline="#FFA500", width=2, fill="", tags="take_profit_area_2", dash=(5, 3)
        )
        self._take_profit_items.append(tp_rect_2)
        
        # Связывающая линия между областями
        tp_center_line = self.canvas.create_line(
            tp_center_x, tp_top, tp_center_x, tp_bottom,
            fill="#FF8C00", width=1, dash=(3, 2)
        )
        self._take_profit_items.append(tp_center_line)
        
        # Метка TAKE PROFIT
        tp_label = self.canvas.create_text(
            tp_left - 40, tp_middle,
            text="TAKE\nPROFIT", fill="#FF8C00", font=("Arial", 9, "bold"), tags="take_profit_area"
        )
        self._take_profit_items.append(tp_label)
        
        # Добавляем интерактивные уголки для изменения размера
        self._add_take_profit_handles(tp_left, tp_top, tp_right, tp_bottom)
        
        print(f"✅ TAKE PROFIT область нарисована: {tp_low_price:.2f}-{tp_high_price:.2f}")
        
    def _add_take_profit_handles(self, left, top, right, bottom):
        """Добавляет интерактивные уголки для TAKE PROFIT области"""
        handle_size = 3
        
        # Четыре угла
        handles = [
            (left, top),      # top-left
            (right, top),     # top-right  
            (left, bottom),   # bottom-left
            (right, bottom)   # bottom-right
        ]
        
        for x, y in handles:
            handle = self.canvas.create_rectangle(
                x - handle_size, y - handle_size,
                x + handle_size, y + handle_size,
                fill="#FF8C00", outline="white", width=1, tags="take_profit_handle"
            )
            self._take_profit_items.append(handle)
            
    def detect_take_profit_area(self, candle_data, fix_area):
        """Детектирует область TAKE PROFIT - флэт перед FIX зоной"""
        if not candle_data or not fix_area:
            return None
            
        fix_start_idx, fix_end_idx, fix_low, fix_high = fix_area[:4]
        
        # Ищем область консолидации/флэта ПЕРЕД движением в FIX
        # Начинаем поиск от начала данных до начала FIX области
        search_end_idx = max(0, fix_start_idx - 5)  # не ближе 5 свечей к FIX
        
        if search_end_idx < 10:  # минимум 10 свечей для анализа
            return None
            
        # Параметры для детекции флэта
        min_consolidation_candles = 8  # минимум 8 свечей в консолидации
        max_volatility_threshold = 0.01  # максимум 1% волатильности для флэта
        
        best_flat_area = None
        best_quality_score = 0
        
        # Сканируем возможные области консолидации
        for start_idx in range(10, search_end_idx - min_consolidation_candles):
            for width in range(min_consolidation_candles, min(25, search_end_idx - start_idx)):
                end_idx = start_idx + width
                
                # Анализируем качество консолидации в этом окне
                consolidation_quality = self._analyze_consolidation_quality(
                    candle_data, start_idx, end_idx
                )
                
                if consolidation_quality > best_quality_score and consolidation_quality > 0.6:
                    # Вычисляем границы области
                    highs = [candle_data[i].high for i in range(start_idx, end_idx)]
                    lows = [candle_data[i].low for i in range(start_idx, end_idx)]
                    
                    tp_high = max(highs)
                    tp_low = min(lows)
                    
                    best_flat_area = (start_idx, end_idx - 1, tp_low, tp_high)
                    best_quality_score = consolidation_quality
                    
        if best_flat_area:
            start_idx, end_idx, tp_low, tp_high = best_flat_area
            print(f"✅ TAKE PROFIT область найдена: свечи {start_idx}-{end_idx}, цены {tp_low:.2f}-{tp_high:.2f}, качество {best_quality_score:.2f}")
            
        return best_flat_area
        
    def _analyze_consolidation_quality(self, candle_data, start_idx, end_idx):
        """Анализирует качество консолидации в заданном диапазоне"""
        if end_idx - start_idx < 5:
            return 0
            
        # Собираем цены закрытия в диапазоне
        closes = [candle_data[i].close for i in range(start_idx, end_idx)]
        highs = [candle_data[i].high for i in range(start_idx, end_idx)]
        lows = [candle_data[i].low for i in range(start_idx, end_idx)]
        
        avg_close = sum(closes) / len(closes)
        max_high = max(highs)
        min_low = min(lows)
        range_size = max_high - min_low
        
        if range_size == 0:
            return 0
            
        # Критерии качества консолидации
        # 1. Низкая волатильность (цены близко к средней)
        volatility_score = 0
        for close in closes:
            deviation = abs(close - avg_close) / avg_close
            if deviation < 0.005:  # отклонение менее 0.5%
                volatility_score += 1
        volatility_score = volatility_score / len(closes)
        
        # 2. Равномерное распределение цен (без резких выбросов)
        range_score = 0
        middle_price = (max_high + min_low) / 2
        for close in closes:
            if abs(close - middle_price) / range_size < 0.3:  # в пределах 30% от диапазона
                range_score += 1
        range_score = range_score / len(closes)
        
        # 3. Минимальная длительность
        duration_score = min(1.0, (end_idx - start_idx) / 15)  # оптимум 15 свечей
        
        # Общий скор качества
        quality_score = (volatility_score * 0.4 + range_score * 0.4 + duration_score * 0.2)
        
        return quality_score
        
    def clear_pattern(self):
        """Очистка FPF паттерна с графика"""
        for items in [self._fix_items, self._ray_items, 
                     self._hi_pattern_items, self._loy_fix_items,
                     getattr(self, '_prefix_items', []),  # добавляем PREFIX
                     self._take_profit_items]:  # добавляем TAKE PROFIT
            for item in items:
                self.canvas.delete(item)
            items.clear()
        
    def update_canvas_size(self, width, height):
        """1=>2;5=85 @07<5@>2 canvas"""
        self.chart_width = min(width - 100, 2000)
        self.chart_height = min(height - 100, 800)
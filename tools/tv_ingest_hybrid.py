#!/usr/bin/env python3
"""
Гибридная версия TV Ingest App
Объединяет лучшие возможности:
- Canvas и визуализация из tv_ingest_app.py 
- Современный OCR и FPF детектор из tv_ingest_new.py
- Binance API загрузчик данных
- Исправления критических багов из базы знаний
"""

print("🚀 Starting Ultimate FPF Bot...")

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sys
import pathlib
from datetime import datetime, timezone, timedelta
import pandas as pd

# Добавляем путь к проекту для импорта модулей
_here = pathlib.Path(__file__).resolve()
_proj_root = _here.parent.parent
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))

# PIL для загрузки и отображения изображений
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    Image = None
    ImageTk = None
    PIL_AVAILABLE = False

# Drag & Drop
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    BaseTk = TkinterDnD.Tk
    DND_AVAILABLE = True
except Exception:
    BaseTk = tk.Tk
    DND_FILES = None
    DND_AVAILABLE = False

# НОВЫЕ МОДУЛИ из улучшенной версии
try:
    from ai.ocr_engine_new import SimpleOCREngine
    OCR_AVAILABLE = True
    print("✅ SimpleOCREngine loaded")
except Exception as e:
    OCR_AVAILABLE = False
    print(f"❌ OCR Engine failed: {e}")

try:
    from core.ai_search_pattern.fpf_detector_new import FpfPatternDetector, FpfPattern
    FPF_AVAILABLE = True
    print("✅ FpfPatternDetector loaded")
except Exception as e:
    FPF_AVAILABLE = False
    print(f"❌ FPF Detector failed: {e}")

try:
    from sync.simple_data_loader import load_data_for_analysis
    DATA_LOADER_AVAILABLE = True  
    print("✅ Data loader loaded")
except Exception as e:
    DATA_LOADER_AVAILABLE = False
    print(f"❌ Data loader failed: {e}")


class HybridTVIngest(BaseTk):
    """Гибридное приложение TV Ingest с полной функциональностью"""
    
    def __init__(self):
        super().__init__()
        self.title("📊 Ultimate FPF Bot - Hybrid Edition")
        
        # Увеличиваем размер окна значительно для лучшего анализа графиков
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        win_w = int(screen_w * 0.85)  # 85% ширины экрана
        win_h = int(screen_h * 0.8)   # 80% высоты экрана
        pos_x = (screen_w - win_w) // 2
        pos_y = (screen_h - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        self.configure(bg="#1c1c1c")
        
        # Устанавливаем минимальный размер окна
        self.minsize(800, 600)
        
        # Окно поверх всех остальных
        try:
            self.attributes('-topmost', True)
            self.lift()
            self.after(200, self.lift)
            print("✅ Window on top")
        except Exception:
            pass
            
        # Инициализация модулей
        self.ocr_engine = SimpleOCREngine() if OCR_AVAILABLE else None
        self.fpf_detector = FpfPatternDetector() if FPF_AVAILABLE else None
        
        # Состояние данных
        self.current_data = None
        self.current_pattern = None
        self.ocr_result = None
        
        # Переменные для редактирования FIX области
        self.dragging_handle = None
        self.dragging_whole_fix = False  # перемещение всего FIX
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.fix_bounds = None  # (left, top, right, bottom)
        self.fix_handles = []  # список ID угловых точек [tl, tr, bl, br]
        self.fix_rect_id = None  # ID основного прямоугольника FIX
        self.original_fix_bounds = None  # сохраняем оригинальные границы
        self.preview_rect = None  # предварительный прямоугольник
        
        self._setup_ui()
        self._setup_canvas()
        
        # Инициализируем status_var перед drag_drop
        self.status_var = tk.StringVar(value="Ready. Drag screenshots here or use Load Image button")
        
        self._setup_drag_drop()
        
        # График состояние (из оригинального приложения)
        self._series_items = []
        self._axis_items = []
        self._series_rows = None
        self._scale_x = 1.0
        self._scale_y = 1.0
        self._offset_x = 0
        self._offset_y = 0
        
        # FPF элементы визуализации
        self._fix_items = []
        self._ray_items = []  
        # self._prefix_items = []  # Убрали PREFIX из текущей итерации
        self._hi_pattern_items = []
        self._loy_fix_items = []
        
        # Сохраненные данные для перерисовки
        self._stored_fix_area = None
        self._stored_ocr_idx = None
        
        
        print("✅ Hybrid TV Ingest initialized")
        
    def _setup_ui(self):
        """Настройка пользовательского интерфейса"""
        
        # Верхняя панель
        top_frame = ttk.Frame(self)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=12, pady=8)
        
        ttk.Label(top_frame, text="📊 Ultimate FPF Bot", 
                 font=("Helvetica", 16, "bold")).pack(side=tk.LEFT)
        
        # Кнопки управления
        ttk.Separator(top_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        
        load_btn = ttk.Button(top_frame, text="📁 Load Image", command=self._load_image)
        load_btn.pack(side=tk.LEFT, padx=4)
        
        analyze_btn = ttk.Button(top_frame, text="🔍 Analyze Pattern", command=self._analyze_pattern)
        analyze_btn.pack(side=tk.LEFT, padx=4)
        
        clear_btn = ttk.Button(top_frame, text="🗑️ Clear", command=self._clear_all)
        clear_btn.pack(side=tk.LEFT, padx=4)
        
        # Статусная панель OCR
        ocr_frame = ttk.Frame(self)
        ocr_frame.pack(side=tk.TOP, fill=tk.X, padx=12, pady=(0, 6))
        
        ttk.Label(ocr_frame, text="Symbol:").pack(side=tk.LEFT)
        self.symbol_var = tk.StringVar()
        ttk.Entry(ocr_frame, textvariable=self.symbol_var, width=12, state='readonly').pack(side=tk.LEFT, padx=(4, 12))
        
        ttk.Label(ocr_frame, text="Timeframe:").pack(side=tk.LEFT)
        self.timeframe_var = tk.StringVar()
        ttk.Entry(ocr_frame, textvariable=self.timeframe_var, width=8, state='readonly').pack(side=tk.LEFT, padx=(4, 12))
        
        ttk.Label(ocr_frame, text="DateTime:").pack(side=tk.LEFT) 
        self.datetime_var = tk.StringVar()
        ttk.Entry(ocr_frame, textvariable=self.datetime_var, width=20, state='readonly').pack(side=tk.LEFT, padx=(4, 12))
        
        # Результаты FPF анализа
        results_frame = ttk.Frame(self)
        results_frame.pack(side=tk.TOP, fill=tk.X, padx=12, pady=(0, 6))
        
        ttk.Label(results_frame, text="🎯 FPF Pattern:").pack(side=tk.LEFT)
        self.pattern_status = tk.StringVar(value="Not analyzed")
        ttk.Entry(results_frame, textvariable=self.pattern_status, width=20, state='readonly').pack(side=tk.LEFT, padx=(4, 12))
        
        ttk.Label(results_frame, text="Confidence:").pack(side=tk.LEFT)
        self.confidence_var = tk.StringVar()
        ttk.Entry(results_frame, textvariable=self.confidence_var, width=10, state='readonly').pack(side=tk.LEFT, padx=(4, 12))
        
    def _setup_canvas(self):
        """Настройка Canvas для графиков"""
        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)
        
        # Привязки для взаимодействия с графиком
        self.canvas.bind('<ButtonPress-1>', self._on_canvas_click)
        self.canvas.bind('<B1-Motion>', self._on_canvas_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_canvas_release)
        self.canvas.bind('<MouseWheel>', self._on_canvas_scroll)
        
        # Привязки для работы с угловыми точками FIX
        self.canvas.bind('<Enter>', self._on_canvas_enter)
        self.canvas.bind('<Motion>', self._on_canvas_motion)
        
        # Убираем проблемные обработчики для стабильности
        
        # Временно отключаем обработчик изменения размера
        # self.bind('<Configure>', self._on_window_resize)
        
    def _setup_drag_drop(self):
        """Настройка Drag & Drop"""
        if DND_AVAILABLE:
            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind('<<Drop>>', self._on_drop)
                self.status("✅ Drag & Drop enabled")
                print("✅ Drag & Drop enabled")
            except Exception as e:
                self.status(f"❌ Drag & Drop failed: {e}")
        else:
            self.status("⚠️ Drag & Drop not available")
            
        # Статусная строка внизу (уже создана в __init__)
        status_label = ttk.Label(self, textvariable=self.status_var)
        status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=8)
        
    def status(self, message):
        """Обновить статусную строку"""
        self.status_var.set(message)
        self.update_idletasks()
        
    def _on_drop(self, event):
        """Обработка Drag & Drop файлов"""
        files = self.tk.splitlist(event.data)
        if files:
            self._load_image_file(files[0])
            
    def _load_image(self):
        """Загрузка изображения через диалог"""
        file_path = filedialog.askopenfilename(
            title="Select TradingView Screenshot",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif"), ("All files", "*.*")]
        )
        if file_path:
            self._load_image_file(file_path)
            
    def _load_image_file(self, file_path):
        """Загрузка и обработка файла изображения"""
        try:
            self.status(f"📁 Loading {file_path}...")
            
            # OCR анализ 
            if self.ocr_engine:
                self.status("🔍 Running OCR analysis...")
                self.ocr_result = self.ocr_engine.extract_chart_info(file_path)
                
                if self.ocr_result:
                    # Обновляем UI с данными OCR
                    self.symbol_var.set(self.ocr_result.get('symbol', 'Unknown'))
                    self.timeframe_var.set(self.ocr_result.get('timeframe', 'Unknown'))
                    self.datetime_var.set(self.ocr_result.get('datetime', 'Not found'))
                    
                    self.status(f"✅ OCR completed: {self.ocr_result.get('symbol')} {self.ocr_result.get('timeframe')}")
                    
                    # Автоматически запускаем анализ (как в базе знаний)
                    self.after(100, self._analyze_pattern)
                else:
                    self.status("❌ OCR failed - could not extract data from image")
            else:
                self.status("❌ OCR engine not available")
                
        except Exception as e:
            self.status(f"❌ Error loading image: {e}")
            messagebox.showerror("Error", f"Failed to load image: {e}")
            
    def _analyze_pattern(self):
        """Анализ FPF паттерна"""
        if not self.ocr_result:
            self.status("❌ No OCR data available for analysis")
            return
            
        try:
            self.status("📊 Loading market data...")
            
            # Загружаем данные
            symbol = self.ocr_result.get('symbol')
            timeframe = self.ocr_result.get('timeframe') 
            target_datetime = self.ocr_result.get('datetime')
            
            if not all([symbol, timeframe, target_datetime]):
                self.status("❌ Incomplete OCR data")
                return
                
            # Используем новый загрузчик данных
            self.current_data = load_data_for_analysis(symbol, timeframe, target_datetime)
            
            if self.current_data is None or len(self.current_data) == 0:
                self.status("❌ No market data loaded")
                return
                
            self.status(f"✅ Loaded {len(self.current_data)} candles")
            
            # Находим индекс OCR свечи (ИСПРАВЛЕНО - используем enumerate)
            ocr_candle_idx = self._find_ocr_candle_index(self.current_data, target_datetime)
            print(f"🎯 OCR candle index: {ocr_candle_idx} (из {len(self.current_data)} свечей)")
            
            if ocr_candle_idx is not None and 0 <= ocr_candle_idx < len(self.current_data):
                ocr_row = self.current_data.iloc[ocr_candle_idx]
                ocr_dt = datetime.fromtimestamp(int(ocr_row['timestamp']) / 1000, tz=timezone.utc)
                print(f"📅 OCR candle time: {ocr_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                print(f"💰 OCR candle OHLC: O={ocr_row['open']:.2f} H={ocr_row['high']:.2f} L={ocr_row['low']:.2f} C={ocr_row['close']:.2f}")
            else:
                print(f"❌ Invalid OCR candle index: {ocr_candle_idx}")
            
            # Рисуем график
            self._draw_chart()
            
            # FPF анализ
            if self.fpf_detector:
                self.status("🔍 Analyzing FPF pattern...")
                
                # Конвертируем в формат для детектора
                candles = []
                for pos_idx, (_, row) in enumerate(self.current_data.iterrows()):  # ИСПРАВЛЕНО
                    candle = (
                        int(row['timestamp']),
                        float(row['open']),
                        float(row['high']), 
                        float(row['low']),
                        float(row['close']),
                        float(row.get('volume', 0))
                    )
                    candles.append(candle)
                    
                # Запускаем детектор
                self.current_pattern = self.fpf_detector.detect_pattern(candles, ocr_candle_idx)
                
                if self.current_pattern:
                    self.pattern_status.set("✅ Pattern Found")
                    self.confidence_var.set(f"{self.current_pattern.confidence:.1%}")
                    self.status(f"✅ FPF Pattern detected with {self.current_pattern.confidence:.1%} confidence")
                    
                    # Рисуем паттерн на графике
                    self._draw_fpf_pattern()
                else:
                    # Даже если полный паттерн не найден, попробуем показать FIX область
                    self._try_draw_partial_pattern(candles, ocr_candle_idx)
                    self.pattern_status.set("❌ No Pattern")
                    self.confidence_var.set("")
                    self.status("❌ No FPF pattern found, but showing partial analysis")
                    
        except Exception as e:
            self.status(f"❌ Analysis failed: {e}")
            print(f"Analysis error: {e}")
            import traceback
            traceback.print_exc()  # Подробная информация об ошибке
            
    def _find_ocr_candle_index(self, data, target_datetime):
        """Поиск индекса свечи ближайшей к OCR времени (ИСПРАВЛЕНО + улучшенный парсинг)"""
        try:
            # Парсим целевую дату с поддержкой разных форматов
            if isinstance(target_datetime, str):
                # Пробуем разные форматы datetime
                try:
                    target_dt = datetime.fromisoformat(target_datetime.replace('Z', '+00:00'))
                except ValueError:
                    # Пробуем другие форматы
                    import dateutil.parser
                    target_dt = dateutil.parser.parse(target_datetime)
            else:
                target_dt = target_datetime
            target_timestamp = int(target_dt.timestamp() * 1000)
            
            # Ищем ближайшую свечу (ИСПРАВЛЕНО - используем enumerate)
            min_diff = float('inf')
            closest_idx = None
            
            for pos_idx, (_, row) in enumerate(data.iterrows()):  # ИСПРАВЛЕНО
                timestamp = int(row['timestamp'])
                diff = abs(timestamp - target_timestamp)
                
                if diff < min_diff:
                    min_diff = diff
                    closest_idx = pos_idx  # позиционный индекс
                    
            return closest_idx
            
        except Exception as e:
            print(f"Error finding OCR candle: {e}")
            return len(data) // 2  # резерв - средина данных
            
    def _draw_chart(self):
        """Рисование графика свечей (адаптировано из оригинального приложения)"""
        if self.current_data is None:
            return
            
        # Очищаем предыдущий график
        self._clear_chart()
        
        # Обновляем canvas и получаем размеры
        self.canvas.update()
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        print(f"🎨 Canvas размеры: {canvas_width}x{canvas_height}")
        
        if canvas_width <= 1 or canvas_height <= 1:
            print("⏳ Canvas не готов, повторяем через 100ms...")
            self.after(100, self._draw_chart)  # Переделаем когда canvas будет готов
            return
            
        # Отступы
        margin_left = 60
        margin_right = 20
        margin_top = 20
        margin_bottom = 60
        
        chart_width = canvas_width - margin_left - margin_right
        chart_height = canvas_height - margin_top - margin_bottom
        
        if chart_width <= 0 or chart_height <= 0:
            return
            
        # Данные для графика
        data_len = len(self.current_data)
        
        # Диапазон цен
        highs = self.current_data['high'].values
        lows = self.current_data['low'].values
        min_price = float(lows.min())
        max_price = float(highs.max())
        price_range = max_price - min_price
        
        if price_range == 0:
            price_range = max_price * 0.01  # избегаем деления на 0
            
        # Рисуем свечи
        candle_width = max(1, chart_width // data_len - 1)
        
        for i in range(data_len):
            row = self.current_data.iloc[i]
            open_price = float(row['open'])
            high_price = float(row['high'])
            low_price = float(row['low'])
            close_price = float(row['close'])
            
            # Позиция X
            x = margin_left + (i * chart_width / data_len)
            
            # Позиции Y (инвертируем так как Y растет вниз)
            high_y = margin_top + (max_price - high_price) * chart_height / price_range
            low_y = margin_top + (max_price - low_price) * chart_height / price_range
            open_y = margin_top + (max_price - open_price) * chart_height / price_range
            close_y = margin_top + (max_price - close_price) * chart_height / price_range
            
            # Цвет свечи - менее насыщенные
            color = "#40cc40" if close_price >= open_price else "#cc4040"  # менее насыщенные зеленая/красная
            
            # Фитиль (high-low линия)
            wick_item = self.canvas.create_line(
                x + candle_width//2, high_y,
                x + candle_width//2, low_y,
                fill=color, width=1
            )
            self._series_items.append(wick_item)
            
            # Тело свечи
            body_top = min(open_y, close_y)
            body_bottom = max(open_y, close_y)
            body_height = max(1, body_bottom - body_top)
            
            body_item = self.canvas.create_rectangle(
                x, body_top,
                x + candle_width, body_bottom,
                fill=color, outline=color
            )
            self._series_items.append(body_item)
            
        # Рисуем оси
        self._draw_axes(margin_left, margin_top, chart_width, chart_height, min_price, max_price)
        
        # Рисуем сохраненные FIX элементы напрямую здесь
        if self._stored_fix_area is not None:
            self._draw_partial_fix_direct(self._stored_fix_area, margin_left, margin_top, chart_width, chart_height, min_price, max_price, data_len)
            
        # if self._stored_ocr_idx is not None:
        #     self._highlight_ocr_candle_direct(self._stored_ocr_idx, margin_left, margin_top, chart_width, chart_height, data_len)  # УБРАНО: YOUR MARK
        
        print(f"✅ Chart drawn: {data_len} candles")
        
    def _draw_axes(self, margin_left, margin_top, chart_width, chart_height, min_price, max_price):
        """Рисование осей и подписей (московское время из базы знаний)"""
        
        # Ось Y (цены) - прозрачнее на 15%
        y_axis = self.canvas.create_line(
            margin_left, margin_top,
            margin_left, margin_top + chart_height,
            fill="#595959", width=1  # серый на 15% прозрачнее
        )
        self._axis_items.append(y_axis)
        
        # Ценовые метки
        price_steps = 5
        price_step = (max_price - min_price) / price_steps
        
        for i in range(price_steps + 1):
            price = min_price + i * price_step
            y = margin_top + chart_height - (i * chart_height / price_steps)
            
            # Горизонтальная линия сетки - прозрачность на 15%  
            grid_line = self.canvas.create_line(
                margin_left, y,
                margin_left + chart_width, y,
                fill="#595959", width=1, dash=(2, 2)  # серый на 15% прозрачнее
            )
            self._axis_items.append(grid_line)
            
            # Ценовая метка
            price_label = self.canvas.create_text(
                margin_left - 5, y,
                text=f"{price:.2f}",
                fill="white", anchor="e", font=("Arial", 8)
            )
            self._axis_items.append(price_label)
            
        # Ось X (время) - ИСПРАВЛЕНО: московское время, прозрачнее на 15%
        x_axis = self.canvas.create_line(
            margin_left, margin_top + chart_height,
            margin_left + chart_width, margin_top + chart_height,
            fill="#595959", width=1  # серый на 15% прозрачнее
        )
        self._axis_items.append(x_axis)
        
        # Временные метки - больше меток по всей ширине
        time_steps = 10  # увеличено с 5 до 10 для лучшего покрытия
        data_len = len(self.current_data)
        
        for i in range(time_steps):
            idx = int(i * data_len / time_steps)
            if idx < data_len:
                row = self.current_data.iloc[idx]
                timestamp = int(row['timestamp'])
                
                # Конвертируем в московское время (UTC+3)
                dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
                moscow_dt = dt + timedelta(hours=3)  # правильное добавление 3 часов
                
                x = margin_left + (i * chart_width / time_steps)
                
                # Вертикальная линия сетки - прозрачность на 15%
                grid_line = self.canvas.create_line(
                    x, margin_top,
                    x, margin_top + chart_height,
                    fill="#595959", width=1, dash=(2, 2)  # серый на 15% прозрачнее
                )
                self._axis_items.append(grid_line)
                
                # Временная метка
                time_label = self.canvas.create_text(
                    x, margin_top + chart_height + 20,
                    text=moscow_dt.strftime('%H:%M\n%m/%d'),
                    fill="white", anchor="n", font=("Arial", 8)
                )
                self._axis_items.append(time_label)
                
    def _draw_fpf_pattern(self):
        """Рисование FPF паттерна на графике"""
        if not self.current_pattern:
            return
            
        # Получаем размеры графика
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        margin_left = 60
        margin_right = 20
        margin_top = 20
        margin_bottom = 60
        chart_width = canvas_width - margin_left - margin_right
        chart_height = canvas_height - margin_top - margin_bottom
        
        data_len = len(self.current_data)
        
        # Диапазон цен
        highs = self.current_data['high'].values
        lows = self.current_data['low'].values
        min_price = float(lows.min())
        max_price = float(highs.max())
        price_range = max_price - min_price
        
        if price_range == 0:
            price_range = max_price * 0.01
            
        def idx_to_x(idx):
            return margin_left + (idx * chart_width / data_len)
            
        def price_to_y(price):
            return margin_top + (max_price - price) * chart_height / price_range
            
        # 1. Рисуем FIX прямоугольник (фиолетовый пунктирный)
        fix_left = idx_to_x(self.current_pattern.fix_start_idx)
        fix_right = idx_to_x(self.current_pattern.fix_end_idx)
        fix_top = price_to_y(self.current_pattern.fix_high)
        fix_bottom = price_to_y(self.current_pattern.fix_low)
        
        fix_rect = self.canvas.create_rectangle(
            fix_left, fix_top, fix_right, fix_bottom,
            outline="#A56BFF", width=2, dash=(5, 3), fill=""
        )
        self._fix_items.append(fix_rect)
        
        fix_label = self.canvas.create_text(
            (fix_left + fix_right) / 2, fix_top - 10,
            text="FIX", fill="#A56BFF", font=("Arial", 10, "bold")
        )
        self._fix_items.append(fix_label)
        
        # 2. Рисуем LOY-FIX точку (красная)
        loy_x = idx_to_x(self.current_pattern.loy_fix_idx)
        loy_y = price_to_y(self.current_pattern.loy_fix_price)
        
        loy_point = self.canvas.create_oval(
            loy_x - 5, loy_y - 5, loy_x + 5, loy_y + 5,
            fill="#ff0000", outline="#ff0000", width=2
        )
        self._loy_fix_items.append(loy_point)
        
        loy_label = self.canvas.create_text(
            loy_x, loy_y - 15,
            text="LOY-FIX", fill="#ff0000", font=("Arial", 8, "bold")
        )
        self._loy_fix_items.append(loy_label)
        
        # 3. Рисуем HI-PATTERN точку (синяя)
        hi_x = idx_to_x(self.current_pattern.hi_pattern_idx)
        hi_y = price_to_y(self.current_pattern.hi_pattern_price)
        
        hi_point = self.canvas.create_oval(
            hi_x - 5, hi_y - 5, hi_x + 5, hi_y + 5,
            fill="#2AA3FF", outline="#2AA3FF", width=2
        )
        self._hi_pattern_items.append(hi_point)
        
        hi_label = self.canvas.create_text(
            hi_x, hi_y - 15,
            text="HI-PATTERN", fill="#2AA3FF", font=("Arial", 8, "bold")
        )
        self._hi_pattern_items.append(hi_label)
        
        # 4. Рисуем RAY линию (желтая горизонтальная)
        ray_y = price_to_y(self.current_pattern.ray_price)
        ray_start_x = fix_right
        ray_end_x = margin_left + chart_width
        
        ray_line = self.canvas.create_line(
            ray_start_x, ray_y, ray_end_x, ray_y,
            fill="#FFD700", width=2, dash=(8, 4)
        )
        self._ray_items.append(ray_line)
        
        ray_label = self.canvas.create_text(
            ray_end_x - 30, ray_y - 10,
            text="RAY", fill="#FFD700", font=("Arial", 10, "bold")
        )
        self._ray_items.append(ray_label)
        
        # 5. PREFIX убран из текущей итерации - фокус на RAY
        
        print("✅ FPF Pattern drawn on chart")
        
    def _try_draw_partial_pattern(self, candles, ocr_candle_idx):
        """Пытается отрисовать частичные результаты анализа (например, только FIX область)"""
        try:
            if not self.fpf_detector:
                return
                
            # Пытаемся найти только FIX область для отрисовки
            candlesticks = []
            for pos_idx, candle_tuple in enumerate(candles):
                from core.ai_search_pattern.fpf_detector_new import CandleData
                candlesticks.append(CandleData.from_tuple(candle_tuple))
            
            # Ищем FIX область тем же улучшенным методом
            fix_area = self.fpf_detector._find_plateau_around_ocr(candlesticks, ocr_candle_idx)
            
            if fix_area:
                print(f"Drawing partial FIX area: {fix_area}")
                # Сохраняем данные для перерисовки
                self._stored_fix_area = fix_area
                self._stored_ocr_idx = ocr_candle_idx
                self._draw_partial_fix(fix_area)
                
                # Попытаемся найти LOY-FIX и HI-PATTERN для полной картины
                loy_fix = self.fpf_detector._find_loy_fix(candlesticks, fix_area)
                hi_pattern = self.fpf_detector._find_hi_pattern(candlesticks, fix_area, loy_fix) if loy_fix else None
                
                if loy_fix:
                    self._draw_partial_loy_fix(loy_fix)
                    print(f"✅ Found LOY-FIX at {loy_fix}")
                
                if hi_pattern:
                    self._draw_partial_hi_pattern(hi_pattern)  
                    print(f"✅ Found HI-PATTERN at {hi_pattern}")
                    
                    # Проверяем валидацию RAY и рисуем его
                    ray_validated_at = self._check_ray_validation_with_drawing(loy_fix, hi_pattern, candlesticks)
                    if ray_validated_at is not None:
                        self._draw_ray_validation(loy_fix, hi_pattern, candles)
                        # self._draw_prefix_area(fix_area, loy_fix, ray_validated_at)  # Убрали PREFIX
                        print(f"✅ RAY validated at index {ray_validated_at}")
                
                # self._highlight_ocr_candle(ocr_candle_idx)  # УБРАНО: не показываем YOUR MARK
                status_parts = ["🟣 FIX"]
                if loy_fix: status_parts.append("🔴 LOY-FIX")
                if hi_pattern: status_parts.append("🟢 HI-PATTERN")
                self.status(f"Showing: {' + '.join(status_parts)}")
            else:
                # Сохраняем только OCR свечу
                self._stored_fix_area = None
                self._stored_ocr_idx = ocr_candle_idx
                # self._highlight_ocr_candle(ocr_candle_idx)  # УБРАНО: не показываем YOUR MARK
                self.status("❌ No FIX area found")
                
        except Exception as e:
            print(f"Error drawing partial pattern: {e}")
            
    def _draw_partial_fix(self, fix_area):
        """Рисует только FIX прямоугольник"""
        start_idx, end_idx, center_price, high_price, low_price = fix_area
        
        # Получаем размеры графика (копируем логику из _draw_fpf_pattern)
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        margin_left = 60
        margin_right = 20
        margin_top = 20
        margin_bottom = 60
        chart_width = canvas_width - margin_left - margin_right
        chart_height = canvas_height - margin_top - margin_bottom
        
        data_len = len(self.current_data)
        
        # Диапазон цен
        highs = self.current_data['high'].values
        lows = self.current_data['low'].values
        min_price = float(lows.min())
        max_price = float(highs.max())
        price_range = max_price - min_price
        
        if price_range == 0:
            price_range = max_price * 0.01
            
        def idx_to_x(idx):
            return margin_left + (idx * chart_width / data_len)
            
        def price_to_y(price):
            return margin_top + (max_price - price) * chart_height / price_range
        
        # Рисуем FIX прямоугольник (фиолетовый пунктирный)
        fix_left = idx_to_x(start_idx)
        fix_right = idx_to_x(end_idx)
        fix_top = price_to_y(high_price)
        fix_bottom = price_to_y(low_price)
        
        fix_rect = self.canvas.create_rectangle(
            fix_left, fix_top, fix_right, fix_bottom,
            outline="#A56BFF", width=3, dash=(5, 3), fill=""
        )
        self._fix_items.append(fix_rect)
        
        # Добавляем угловые точки для редактирования (8x8 пикселей)
        handle_size = 4
        
        # Верхний левый угол
        tl_handle = self.canvas.create_rectangle(
            fix_left - handle_size, fix_top - handle_size, 
            fix_left + handle_size, fix_top + handle_size,
            fill="#A56BFF", outline="white", width=1, tags="fix_handle"
        )
        self._fix_items.append(tl_handle)
        
        # Верхний правый угол  
        tr_handle = self.canvas.create_rectangle(
            fix_right - handle_size, fix_top - handle_size,
            fix_right + handle_size, fix_top + handle_size, 
            fill="#A56BFF", outline="white", width=1, tags="fix_handle"
        )
        self._fix_items.append(tr_handle)
        
        # Нижний левый угол
        bl_handle = self.canvas.create_rectangle(
            fix_left - handle_size, fix_bottom - handle_size,
            fix_left + handle_size, fix_bottom + handle_size,
            fill="#A56BFF", outline="white", width=1, tags="fix_handle" 
        )
        self._fix_items.append(bl_handle)
        
        # Нижний правый угол
        br_handle = self.canvas.create_rectangle(
            fix_right - handle_size, fix_bottom - handle_size,
            fix_right + handle_size, fix_bottom + handle_size,
            fill="#A56BFF", outline="white", width=1, tags="fix_handle"
        )
        self._fix_items.append(br_handle)
        
        fix_label = self.canvas.create_text(
            (fix_left + fix_right) / 2, fix_top - 15,
            text="🟣 FIX", fill="#A56BFF", font=("Arial", 12, "bold")
        )
        self._fix_items.append(fix_label)
        
        # Сохраняем границы FIX области и ID угловых точек для редактирования
        self.fix_bounds = (fix_left, fix_top, fix_right, fix_bottom)
        self.fix_handles = [tl_handle, tr_handle, bl_handle, br_handle]
        
        print(f"✅ Partial FIX drawn: {start_idx}-{end_idx} @ {low_price:.2f}-{high_price:.2f}")
        
    def _redraw_fix_area(self, left, top, right, bottom):
        """Перерисовывает FIX область с новыми границами"""
        # Основной прямоугольник
        fix_rect = self.canvas.create_rectangle(
            left, top, right, bottom,
            outline="#A56BFF", width=3, dash=(5, 3), fill="", tags="fix_rect"
        )
        self._fix_items.append(fix_rect)
        self.fix_rect_id = fix_rect  # сохраняем ID для перемещения
        
        # Угловые точки
        handle_size = 4
        
        # Верхний левый угол
        tl_handle = self.canvas.create_rectangle(
            left - handle_size, top - handle_size, 
            left + handle_size, top + handle_size,
            fill="#A56BFF", outline="white", width=1, tags="fix_handle"
        )
        self._fix_items.append(tl_handle)
        
        # Верхний правый угол  
        tr_handle = self.canvas.create_rectangle(
            right - handle_size, top - handle_size,
            right + handle_size, top + handle_size, 
            fill="#A56BFF", outline="white", width=1, tags="fix_handle"
        )
        self._fix_items.append(tr_handle)
        
        # Нижний левый угол
        bl_handle = self.canvas.create_rectangle(
            left - handle_size, bottom - handle_size,
            left + handle_size, bottom + handle_size,
            fill="#A56BFF", outline="white", width=1, tags="fix_handle" 
        )
        self._fix_items.append(bl_handle)
        
        # Нижний правый угол
        br_handle = self.canvas.create_rectangle(
            right - handle_size, bottom - handle_size,
            right + handle_size, bottom + handle_size,
            fill="#A56BFF", outline="white", width=1, tags="fix_handle"
        )
        self._fix_items.append(br_handle)
        
        # Подпись
        fix_label = self.canvas.create_text(
            (left + right) / 2, top - 15,
            text="🟣 FIX", fill="#A56BFF", font=("Arial", 12, "bold")
        )
        self._fix_items.append(fix_label)
        
        # Обновляем сохраненные данные
        self.fix_bounds = (left, top, right, bottom)
        self.fix_handles = [tl_handle, tr_handle, bl_handle, br_handle]
        
    def _draw_partial_loy_fix(self, loy_fix):
        """Рисует LOY-FIX точку для частичного паттерна"""
        if not loy_fix or self.current_data is None:
            return
            
        loy_idx, loy_price = loy_fix
        
        # Используем те же координаты что и для FIX
        margin_left = 40
        margin_top = 40
        chart_width = 2000
        chart_height = 800
        data_len = len(self.current_data)
        
        highs = self.current_data['high'].values
        lows = self.current_data['low'].values
        min_price = float(lows.min())
        max_price = float(highs.max())
        price_range = max_price - min_price
        
        if price_range == 0:
            price_range = max_price * 0.01
            
        def idx_to_x(idx):
            return margin_left + (idx * chart_width / data_len)
            
        def price_to_y(price):
            return margin_top + (max_price - price) * chart_height / price_range
        
        # Рисуем LOY-FIX точку (красная)
        loy_x = idx_to_x(loy_idx)
        loy_y = price_to_y(loy_price)
        
        loy_point = self.canvas.create_oval(
            loy_x - 3, loy_y - 3, loy_x + 3, loy_y + 3,
            fill="#FF4444", outline="white", width=1
        )
        self._loy_fix_items.append(loy_point)
        
        loy_label = self.canvas.create_text(
            loy_x, loy_y + 20,
            text="🔴 LOY-FIX", fill="#FF4444", font=("Arial", 10, "bold")
        )
        self._loy_fix_items.append(loy_label)
        
    def _draw_partial_hi_pattern(self, hi_pattern):
        """Рисует HI-PATTERN точку для частичного паттерна"""
        if not hi_pattern or self.current_data is None:
            return
            
        hi_idx, hi_price = hi_pattern
        
        # Используем те же координаты что и для FIX
        margin_left = 40
        margin_top = 40
        chart_width = 2000
        chart_height = 800
        data_len = len(self.current_data)
        
        highs = self.current_data['high'].values
        lows = self.current_data['low'].values
        min_price = float(lows.min())
        max_price = float(highs.max())
        price_range = max_price - min_price
        
        if price_range == 0:
            price_range = max_price * 0.01
            
        def idx_to_x(idx):
            return margin_left + (idx * chart_width / data_len)
            
        def price_to_y(price):
            return margin_top + (max_price - price) * chart_height / price_range
        
        # Рисуем HI-PATTERN точку (зелёная)
        hi_x = idx_to_x(hi_idx)
        hi_y = price_to_y(hi_price)
        
        hi_point = self.canvas.create_oval(
            hi_x - 6, hi_y - 6, hi_x + 6, hi_y + 6,
            fill="#44FF44", outline="white", width=2
        )
        self._hi_pattern_items.append(hi_point)
        
        hi_label = self.canvas.create_text(
            hi_x, hi_y - 20,
            text="🟢 HI-PATTERN", fill="#44FF44", font=("Arial", 10, "bold")
        )
        self._hi_pattern_items.append(hi_label)
        
    def _draw_ray_validation(self, loy_fix, hi_pattern, candles_data):
        """Рисует RAY - горизонтальную линию валидации от LOY-FIX"""
        if not loy_fix or not hi_pattern or not candles_data:
            return
            
        loy_idx, loy_price = loy_fix
        hi_idx, hi_price = hi_pattern
        
        # Используем те же координаты что и для других элементов
        margin_left = 40
        margin_top = 40
        chart_width = 2000
        chart_height = 800
        data_len = len(self.current_data)
        
        highs = self.current_data['high'].values
        lows = self.current_data['low'].values
        min_price = float(lows.min())
        max_price = float(highs.max())
        price_range = max_price - min_price
        
        if price_range == 0:
            price_range = max_price * 0.01
            
        def idx_to_x(idx):
            return margin_left + (idx * chart_width / data_len)
            
        def price_to_y(price):
            return margin_top + (max_price - price) * chart_height / price_range
        
        # Находим первую свечу после HI-PATTERN, которая пробила RAY на 1-2 тика
        ray_start_x = idx_to_x(loy_idx)
        ray_y = price_to_y(loy_price)
        ray_end_x = ray_start_x
        
        # Ищем где цена пробила RAY вниз
        for i in range(hi_idx + 1, min(len(candles_data), hi_idx + 50)):
            candle_low = candles_data[i][3]  # low price
            if candle_low < (loy_price - 0.02):  # пробили на 2 тика вниз
                ray_end_x = idx_to_x(i)
                break
        
        # Рисуем RAY линию только вправо от LOY-FIX
        if ray_end_x == ray_start_x:  # если не нашли пробой, рисуем на 300 пикселей вправо
            ray_end_x = min(ray_start_x + 300, chart_width + margin_left)
        
        ray_line = self.canvas.create_line(
            ray_start_x, ray_y, ray_end_x, ray_y,
            fill="#FFD700", width=2, dash=(5, 3)
        )
        self._ray_items.append(ray_line)
        
        ray_label = self.canvas.create_text(
            ray_end_x + 10, ray_y,
            text="RAY", fill="#FFD700", font=("Arial", 8, "bold")
        )
        self._ray_items.append(ray_label)
        
    def _draw_prefix_area(self, fix_area, loy_fix, ray_validated_at):
        """Рисует PREFIX область - целевую зону для шорта (ОТКЛЮЧЕНО - фокус на RAY)"""
        return  # Отключили PREFIX в текущей итерации
        if not fix_area or not loy_fix or ray_validated_at is None:
            return
            
        # PREFIX по высоте равен области FIX
        fix_high = fix_area[3]
        fix_low = fix_area[4] 
        fix_height = fix_high - fix_low
        
        # PREFIX область по высоте равна FIX, цена чаще идет ниже LOY-FIX
        loy_price = loy_fix[1]
        prefix_bottom = loy_price - fix_height * 0.5  # начинаем ниже LOY-FIX
        prefix_top = prefix_bottom + fix_height
        
        # По горизонтали - от точки валидации RAY вправо
        margin_left = 40
        chart_width = 2000
        data_len = len(self.current_data)
        
        def idx_to_x(idx):
            return margin_left + (idx * chart_width / data_len)
            
        highs = self.current_data['high'].values
        lows = self.current_data['low'].values
        min_price = float(lows.min())
        max_price = float(highs.max())
        price_range = max_price - min_price
        margin_top = 40
        chart_height = 800
        
        if price_range == 0:
            price_range = max_price * 0.01
            
        def price_to_y(price):
            return margin_top + (max_price - price) * chart_height / price_range
        
        prefix_left = idx_to_x(ray_validated_at)
        prefix_right = min(prefix_left + 200, chart_width + margin_left)  # ограничиваем ширину
        prefix_top_y = price_to_y(prefix_top)
        prefix_bottom_y = price_to_y(prefix_bottom)
        
        # Рисуем PREFIX прямоугольник (зеленый пунктирный)
        prefix_rect = self.canvas.create_rectangle(
            prefix_left, prefix_top_y, prefix_right, prefix_bottom_y,
            outline="#00FF00", width=2, dash=(3, 3), fill="#00FF0020"
        )
        self._prefix_items.append(prefix_rect)
        
        prefix_label = self.canvas.create_text(
            prefix_left + 50, prefix_top_y - 15,
            text="🟢 PREFIX", fill="#00FF00", font=("Arial", 10, "bold")
        )
        self._prefix_items.append(prefix_label)
        
    def _check_ray_validation_with_drawing(self, loy_fix, hi_pattern, candlesticks):
        """Проверяет валидацию RAY - где цена пробила уровень LOY-FIX на 1-2 тика вниз"""
        if not loy_fix or not hi_pattern:
            return None
            
        loy_idx, loy_price = loy_fix
        hi_idx, hi_price = hi_pattern
        
        # Ищем где цена после HI-PATTERN пробила RAY уровень вниз
        for i in range(hi_idx + 1, min(len(candlesticks), hi_idx + 100)):
            candle_low = candlesticks[i].low
            if candle_low < (loy_price - 0.02):  # пробили на 2 тика (0.02) вниз
                print(f"RAY validation: candle {i} broke below {loy_price:.2f} at {candle_low:.2f}")
                return i  # возвращаем индекс где произошла валидация
                
        return None  # RAY не валидирован
        
    def _highlight_ocr_candle(self, ocr_idx):
        """Подсвечивает OCR свечу (которую обозначил пользователь)"""
        if ocr_idx is None or self.current_data is None:
            return
            
        # Получаем размеры графика
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        margin_left = 60
        margin_right = 20
        margin_top = 20
        margin_bottom = 60
        chart_width = canvas_width - margin_left - margin_right
        chart_height = canvas_height - margin_top - margin_bottom
        
        data_len = len(self.current_data)
        
        # Позиция OCR свечи
        candle_width = max(1, chart_width // data_len - 1)
        x = margin_left + (ocr_idx * chart_width / data_len)
        
        # Рисуем подсветку OCR свечи (оранжевая обводка)
        highlight = self.canvas.create_rectangle(
            x - 2, margin_top - 2,
            x + candle_width + 2, margin_top + chart_height + 2,
            outline="#FF6600", width=2, dash=(3, 3), fill=""
        )
        self._fix_items.append(highlight)
        
        # Подпись
        ocr_label = self.canvas.create_text(
            x + candle_width//2, margin_top + chart_height + 40,
            text="📍 YOUR MARK", fill="#FF6600", font=("Arial", 9, "bold")
        )
        self._fix_items.append(ocr_label)
        
    def _draw_partial_fix_direct(self, fix_area, margin_left, margin_top, chart_width, chart_height, min_price, max_price, data_len):
        """Рисует FIX прямоугольник напрямую с переданными параметрами"""
        start_idx, end_idx, center_price, high_price, low_price = fix_area
        
        price_range = max_price - min_price
        if price_range == 0:
            price_range = max_price * 0.01
            
        def idx_to_x(idx):
            return margin_left + (idx * chart_width / data_len)
            
        def price_to_y(price):
            return margin_top + (max_price - price) * chart_height / price_range
        
        # Рисуем FIX прямоугольник (фиолетовый пунктирный)
        fix_left = idx_to_x(start_idx)
        fix_right = idx_to_x(end_idx)
        fix_top = price_to_y(high_price)
        fix_bottom = price_to_y(low_price)
        
        fix_rect = self.canvas.create_rectangle(
            fix_left, fix_top, fix_right, fix_bottom,
            outline="#A56BFF", width=3, dash=(5, 3), fill=""
        )
        self._fix_items.append(fix_rect)
        
        fix_label = self.canvas.create_text(
            (fix_left + fix_right) / 2, fix_top - 15,
            text="🟣 FIX", fill="#A56BFF", font=("Arial", 12, "bold")
        )
        self._fix_items.append(fix_label)
        
    def _highlight_ocr_candle_direct(self, ocr_idx, margin_left, margin_top, chart_width, chart_height, data_len):
        """Подсвечивает OCR свечу напрямую с переданными параметрами"""
        candle_width = max(1, chart_width // data_len - 1)
        x = margin_left + (ocr_idx * chart_width / data_len)
        
        # Рисуем подсветку OCR свечи (оранжевая обводка)
        highlight = self.canvas.create_rectangle(
            x - 2, margin_top - 2,
            x + candle_width + 2, margin_top + chart_height + 2,
            outline="#FF6600", width=2, dash=(3, 3), fill=""
        )
        self._fix_items.append(highlight)
        
        # Подпись
        ocr_label = self.canvas.create_text(
            x + candle_width//2, margin_top + chart_height + 40,
            text="📍 YOUR MARK", fill="#FF6600", font=("Arial", 9, "bold")
        )
        self._fix_items.append(ocr_label)
        
    def _redraw_stored_elements(self):
        """Перерисовывает сохраненные FIX элементы после обновления canvas"""
        # Сначала очищаем старые FIX элементы чтобы избежать наложения
        for item in self._fix_items:
            try:
                self.canvas.delete(item)
            except:
                pass
        self._fix_items.clear()
        
        # Теперь перерисовываем сохраненные элементы
        if self._stored_fix_area is not None:
            self._draw_partial_fix(self._stored_fix_area)
            
        if self._stored_ocr_idx is not None:
            self._highlight_ocr_candle(self._stored_ocr_idx)
        
    def _clear_chart(self):
        """Очистка графика"""
        # Удаляем элементы графика
        for item in self._series_items + self._axis_items:
            self.canvas.delete(item)
        self._series_items.clear()
        self._axis_items.clear()
        
        # Удаляем FPF элементы
        self._clear_fpf_pattern()
        
    def _clear_fpf_pattern(self):
        """Очистка FPF паттерна с графика"""
        for items in [self._fix_items, self._ray_items,  # self._prefix_items, 
                     self._hi_pattern_items, self._loy_fix_items]:
            for item in items:
                self.canvas.delete(item)
            items.clear()
            
        # Очищаем сохраненные данные
        self._stored_fix_area = None
        self._stored_ocr_idx = None
            
    def _clear_all(self):
        """Полная очистка"""
        self._clear_chart()
        
        # Сброс данных
        self.current_data = None
        self.current_pattern = None
        self.ocr_result = None
        
        # Сброс UI
        self.symbol_var.set("")
        self.timeframe_var.set("")
        self.datetime_var.set("")
        self.pattern_status.set("Not analyzed")
        self.confidence_var.set("")
        
        self.status("🗑️ Cleared all data")
        
    # Обработчики событий Canvas и окна
    def _on_canvas_click(self, event):
        """Клик по canvas - начало перетаскивания угловой точки или всего FIX"""
        # Проверяем, кликнули ли мы на элемент FIX
        clicked_item = self.canvas.find_closest(event.x, event.y)[0]
        item_tags = self.canvas.gettags(clicked_item)
        
        if "fix_handle" in item_tags:
            # Клик по угловой точке - изменение размера
            self.dragging_handle = clicked_item
            self.dragging_whole_fix = False
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            # Сохраняем оригинальные границы для восстановления
            if self.fix_bounds:
                self.original_fix_bounds = self.fix_bounds
            self.canvas.config(cursor="fleur")  # Меняем курсор
            
        elif "fix_rect" in item_tags or clicked_item == self.fix_rect_id:
            # Клик по основному прямоугольнику - перемещение всего FIX
            self.dragging_whole_fix = True
            self.dragging_handle = None
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            # Сохраняем оригинальные границы для перемещения
            if self.fix_bounds:
                self.original_fix_bounds = self.fix_bounds
            self.canvas.config(cursor="move")  # Курсор для перемещения
        
    def _on_canvas_drag(self, event):
        """Перетаскивание по canvas - показываем предварительный размер или перемещение"""
        if self.dragging_whole_fix and self.original_fix_bounds:
            # Перемещение всего FIX прямоугольника
            dx = event.x - self.drag_start_x
            dy = event.y - self.drag_start_y
            
            # Получаем оригинальные границы и смещаем их
            left, top, right, bottom = self.original_fix_bounds
            new_left = left + dx
            new_top = top + dy
            new_right = right + dx
            new_bottom = bottom + dy
            
            # Удаляем старый предварительный прямоугольник
            if self.preview_rect:
                self.canvas.delete(self.preview_rect)
            
            # Показываем новый предварительный прямоугольник для перемещения (зелёный)
            self.preview_rect = self.canvas.create_rectangle(
                new_left, new_top, new_right, new_bottom,
                outline="#6BFF6B", width=2, dash=(3, 2), fill=""
            )
            
        elif self.dragging_handle and self.original_fix_bounds and self.fix_handles:
            # Определяем какой угол тащим
            handle_index = None
            for i, handle in enumerate(self.fix_handles):
                if handle == self.dragging_handle:
                    handle_index = i
                    break
            
            if handle_index is not None:
                # Получаем оригинальные границы
                left, top, right, bottom = self.original_fix_bounds
                
                # Изменяем границы в зависимости от того, какой угол тащим
                if handle_index == 0:  # Верхний левый
                    left = event.x
                    top = event.y
                elif handle_index == 1:  # Верхний правый
                    right = event.x  
                    top = event.y
                elif handle_index == 2:  # Нижний левый
                    left = event.x
                    bottom = event.y
                elif handle_index == 3:  # Нижний правый
                    right = event.x
                    bottom = event.y
                
                # Проверяем что границы корректны
                if right > left and bottom > top:
                    # Удаляем старый предварительный прямоугольник
                    if self.preview_rect:
                        self.canvas.delete(self.preview_rect)
                    
                    # Показываем новый предварительный прямоугольник (более яркий)
                    self.preview_rect = self.canvas.create_rectangle(
                        left, top, right, bottom,
                        outline="#FF6BFF", width=2, dash=(3, 2), fill=""
                    )
            
    def _on_canvas_release(self, event):
        """Отпускание кнопки мыши - завершение перетаскивания"""
        if self.dragging_whole_fix and self.original_fix_bounds:
            # Завершение перемещения всего FIX прямоугольника
            dx = event.x - self.drag_start_x
            dy = event.y - self.drag_start_y
            
            # Рассчитываем финальные границы
            left, top, right, bottom = self.original_fix_bounds
            new_left = left + dx
            new_top = top + dy
            new_right = right + dx
            new_bottom = bottom + dy
            
            # Удаляем предварительный прямоугольник
            if self.preview_rect:
                self.canvas.delete(self.preview_rect)
                self.preview_rect = None
            
            # Удаляем старые элементы FIX
            for item in self._fix_items:
                self.canvas.delete(item)
            self._fix_items.clear()
            
            # Рисуем финальный FIX прямоугольник в новом месте
            self._redraw_fix_area(new_left, new_top, new_right, new_bottom)
            
        elif self.dragging_handle and self.original_fix_bounds and self.fix_handles:
            # Определяем какой угол тащили
            handle_index = None
            for i, handle in enumerate(self.fix_handles):
                if handle == self.dragging_handle:
                    handle_index = i
                    break
            
            if handle_index is not None:
                # Рассчитываем финальные границы
                left, top, right, bottom = self.original_fix_bounds
                
                if handle_index == 0:  # Верхний левый
                    left = event.x
                    top = event.y
                elif handle_index == 1:  # Верхний правый
                    right = event.x  
                    top = event.y
                elif handle_index == 2:  # Нижний левый
                    left = event.x
                    bottom = event.y
                elif handle_index == 3:  # Нижний правый
                    right = event.x
                    bottom = event.y
                
                # Проверяем что границы корректны
                if right > left and bottom > top:
                    # Удаляем предварительный прямоугольник
                    if self.preview_rect:
                        self.canvas.delete(self.preview_rect)
                        self.preview_rect = None
                    
                    # Удаляем старые элементы FIX
                    for item in self._fix_items:
                        self.canvas.delete(item)
                    self._fix_items.clear()
                    
                    # Рисуем финальный FIX прямоугольник с новыми размерами
                    self._redraw_fix_area(left, top, right, bottom)
            
        # Сбрасываем состояние перетаскивания
        self.dragging_handle = None
        self.dragging_whole_fix = False
        self.original_fix_bounds = None
        self.canvas.config(cursor="")  # Возвращаем обычный курсор
        
    def _on_canvas_scroll(self, event):
        """Прокрутка canvas"""
        pass
        
    def _on_canvas_enter(self, event):
        """Вход мыши в область canvas"""
        pass
        
    def _on_canvas_motion(self, event):
        """Движение мыши по canvas - подсветка угловых точек и основного прямоугольника"""
        if not self.dragging_handle and not self.dragging_whole_fix:
            try:
                # Проверяем, находится ли курсор над элементами FIX
                closest_items = self.canvas.find_closest(event.x, event.y)
                if closest_items:
                    item_under_cursor = closest_items[0]
                    item_tags = self.canvas.gettags(item_under_cursor)
                    
                    if "fix_handle" in item_tags:
                        self.canvas.config(cursor="fleur")  # Курсор изменения размера
                    elif "fix_rect" in item_tags or item_under_cursor == self.fix_rect_id:
                        self.canvas.config(cursor="move")   # Курсор перемещения
                    else:
                        self.canvas.config(cursor="")       # Обычный курсор
            except (IndexError, tk.TclError):
                # Игнорируем ошибки при поиске элементов
                pass
        
    def _on_window_resize(self, event):
        """Обработчик изменения размера окна - перерисовываем график"""
        # Перерисовываем только если есть данные и это главное окно (не canvas)
        if hasattr(self, 'current_data') and self.current_data is not None and event.widget == self:
            self.after(100, self._draw_chart)  # небольшая задержка для стабильности

    def _on_canvas_event(self, event):
        """Универсальный обработчик событий canvas"""
        # Простая проверка без цикла перерисовки
        pass


def main():
    """Запуск приложения"""
    try:
        app = HybridTVIngest()
        app.status("🚀 Ultimate FPF Bot ready!")
        app.mainloop()
    except Exception as e:
        print(f"❌ App failed to start: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
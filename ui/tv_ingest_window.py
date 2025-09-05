"""
UI компонент для TV Ingest - окно и интерфейс
Извлечен из tv_ingest_hybrid.py для модульности
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sys
import pathlib

# Добавляем путь к проекту
_here = pathlib.Path(__file__).resolve()
_proj_root = _here.parent.parent
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))

# Drag & Drop
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    BaseTk = TkinterDnD.Tk
    DND_AVAILABLE = True
except Exception:
    BaseTk = tk.Tk
    DND_FILES = None
    DND_AVAILABLE = False

# PIL для изображений  
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    Image = None
    ImageTk = None
    PIL_AVAILABLE = False


class TVIngestWindow(BaseTk):
    """Окно TV Ingest для анализа паттернов FPF"""
    
    def __init__(self):
        super().__init__()
        self.current_data = None
        self.current_image_path = None
        
        # Коллбеки для внешней логики (паттерн Strategy)
        self.on_image_loaded = None
        self.on_pattern_analyze = None
        self.on_fix_area_changed = None  # Коллбек для изменения FIX области
        self.on_take_profit_area_changed = None  # Коллбек для изменения TAKE PROFIT области
        
        self._setup_ui()
        self._setup_canvas()
        self._setup_drag_drop()
        
        print("✅ Hybrid TV Ingest initialized")
        
    def _setup_ui(self):
        """Настройка интерфейса"""
        self.title("🎯 Ultimate FPF Bot - Trading Pattern Detection")
        self.geometry("1200x800")
        
        # Всегда наверху
        self.attributes("-topmost", True)
        print("✅ Window on top")
        
        # Статус бар
        self.status_var = tk.StringVar()
        self.status_var.set("Ready to analyze FPF patterns")
        
        status_frame = ttk.Frame(self)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=2)
        
        ttk.Label(status_frame, textvariable=self.status_var, 
                 font=("Arial", 9)).pack(side=tk.LEFT)
        
        # Кнопки
        button_frame = ttk.Frame(self)
        button_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Button(button_frame, text="📁 Load Screenshot", 
                  command=self._load_image_dialog).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(button_frame, text="🔍 Analyze FPF", 
                  command=self._analyze_pattern).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(button_frame, text="🗑️ Clear Chart", 
                  command=self._clear_chart).pack(side=tk.LEFT, padx=2)
                  
    def _setup_canvas(self):
        """Настройка canvas для графиков"""
        self.canvas = tk.Canvas(self, bg="#1a1a1a")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Привязка событий мыши для интерактивности
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        
        # Обработка изменения размера canvas для обновления паттернов FPF
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        # Состояние перетаскивания
        self._dragging = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._drag_item = None
        
    def _setup_drag_drop(self):
        """Настройка drag & drop файлов"""
        if DND_AVAILABLE:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self._on_drop)
            print("✅ Drag & Drop enabled")
        else:
            print("❌ Drag & Drop not available")
            
    def _on_drop(self, event):
        """Обработка перетаскивания файла"""
        if hasattr(event, 'data'):
            files = self.tk.splitlist(event.data)
            if files:
                self._load_image_file(files[0])
                
    def _load_image_dialog(self):
        """Диалог загрузки изображения"""
        file_path = filedialog.askopenfilename(
            title="Select TradingView screenshot",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            self._load_image_file(file_path)
            
    def _load_image_file(self, file_path):
        """Загрузка файла изображения"""
        try:
            self.current_image_path = file_path
            self.status(f"📷 Loaded: {pathlib.Path(file_path).name}")
            
            # Вызываем коллбек если есть
            if self.on_image_loaded:
                self.on_image_loaded(file_path)
                
        except Exception as e:
            self.status(f"❌ Error loading image: {e}")
            messagebox.showerror("Error", f"Failed to load image: {e}")
            
    def _analyze_pattern(self):
        """Запуск анализа паттерна"""
        if not self.current_image_path:
            self.status("❌ No image loaded")
            messagebox.showwarning("Warning", "Please load a TradingView screenshot first")
            return
            
        try:
            self.status("🔍 Analyzing FPF pattern...")
            # Вызываем коллбек если есть
            if self.on_pattern_analyze:
                self.on_pattern_analyze()
            else:
                self.status("❌ Pattern analyzer not connected")
        except Exception as e:
            self.status(f"❌ Analysis error: {e}")
            messagebox.showerror("Error", f"Pattern analysis failed: {e}")
            
    def _clear_chart(self):
        """Очистка графика"""
        self.canvas.delete("all")
        self.status("🗑️ Chart cleared")
        
    def _on_canvas_configure(self, event):
        """Обработка изменения размера canvas - обновляем элементы FPF"""
        # Коллбек для обновления паттернов при изменении размера
        if hasattr(self, 'on_canvas_resize') and self.on_canvas_resize:
            self.on_canvas_resize(event)
        
    def _on_canvas_click(self, event):
        """Обработка клика по canvas"""
        self._dragging = False
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        
        # Проверяем клик по элементам
        item = self.canvas.find_closest(event.x, event.y)[0]
        tags = self.canvas.gettags(item)
        
        if "fix_handle" in tags or "fix_area" in tags:
            self._dragging = True
            self._drag_item = item
            print(f"🎯 Started dragging FIX element: {tags}")
        elif "take_profit_handle" in tags or "take_profit_area" in tags:
            self._dragging = True
            self._drag_item = item
            print(f"🎯 Started dragging TAKE PROFIT element: {tags}")
            
    def _on_canvas_drag(self, event):
        """Обработка перетаскивания по canvas"""
        if self._dragging and self._drag_item:
            dx = event.x - self._drag_start_x
            dy = event.y - self._drag_start_y
            
            # Обработка перетаскивания элементов FIX и TAKE PROFIT
            tags = self.canvas.gettags(self._drag_item)
            if "fix_handle" in tags:
                # Изменение размера FIX области через уголки
                self._resize_fix_area(self._drag_item, dx, dy)
                print(f"🎯 Resizing FIX area via handle: dx={dx}, dy={dy}")
            elif "fix_area" in tags:
                # Перемещение всей FIX области как группы
                for item in self.canvas.find_withtag("fix_area"):
                    self.canvas.move(item, dx, dy)
                for item in self.canvas.find_withtag("fix_handle"):
                    self.canvas.move(item, dx, dy)
                print(f"🎯 Moving FIX group by dx={dx}, dy={dy}")
                
                # Уведомляем о изменении FIX области
                self._notify_fix_area_changed()
            elif "take_profit_handle" in tags:
                # Изменение размера TAKE PROFIT области через уголки
                self._resize_take_profit_area(self._drag_item, dx, dy)
                print(f"🎯 Resizing TAKE PROFIT area via handle: dx={dx}, dy={dy}")
            elif "take_profit_area" in tags or "take_profit_area_1" in tags or "take_profit_area_2" in tags:
                # Перемещение всей TAKE PROFIT области как группы
                for item in self.canvas.find_withtag("take_profit_area"):
                    self.canvas.move(item, dx, dy)
                for item in self.canvas.find_withtag("take_profit_area_1"):
                    self.canvas.move(item, dx, dy)
                for item in self.canvas.find_withtag("take_profit_area_2"):
                    self.canvas.move(item, dx, dy)
                for item in self.canvas.find_withtag("take_profit_handle"):
                    self.canvas.move(item, dx, dy)
                print(f"🎯 Moving TAKE PROFIT group by dx={dx}, dy={dy}")
                
                # Уведомляем о изменении TAKE PROFIT области
                self._notify_take_profit_area_changed()
            else:
                # Обычное перемещение одного элемента
                self.canvas.move(self._drag_item, dx, dy)
            
            self._drag_start_x = event.x
            self._drag_start_y = event.y
            
    def _resize_fix_area(self, handle_item, dx, dy):
        """Изменение размера FIX области через уголки"""
        # Находим прямоугольник FIX области
        fix_rect = None
        for item in self.canvas.find_withtag("fix_area"):
            if self.canvas.type(item) == "rectangle":
                fix_rect = item
                break
        
        if not fix_rect:
            return
            
        # Получаем текущие координаты прямоугольника
        coords = self.canvas.coords(fix_rect)
        left, top, right, bottom = coords
        
        # Получаем координаты уголка
        handle_coords = self.canvas.coords(handle_item)
        handle_x = (handle_coords[0] + handle_coords[2]) / 2
        handle_y = (handle_coords[1] + handle_coords[3]) / 2
        
        # Определяем какой это уголок и изменяем соответствующую сторону
        if abs(handle_x - left) < abs(handle_x - right):  # левая сторона
            left += dx
        else:  # правая сторона
            right += dx
            
        if abs(handle_y - top) < abs(handle_y - bottom):  # верхняя сторона
            top += dy
        else:  # нижняя сторона
            bottom += dy
            
        # Обновляем координаты прямоугольника
        self.canvas.coords(fix_rect, left, top, right, bottom)
        
        # Перемещаем только этот уголок
        self.canvas.move(handle_item, dx, dy)
        
        # Обновляем остальные уголки к новым координатам прямоугольника
        self._update_fix_handles(left, top, right, bottom, exclude_handle=handle_item)
        
        # Уведомляем о изменении FIX области
        self._notify_fix_area_changed()
    
    def _update_fix_handles(self, left, top, right, bottom, exclude_handle=None):
        """Обновление позиций уголков FIX области"""
        handle_size = 4
        handles_coords = [
            (left, top),      # top-left
            (right, top),     # top-right  
            (left, bottom),   # bottom-left
            (right, bottom)   # bottom-right
        ]
        
        handle_items = [item for item in self.canvas.find_withtag("fix_handle") 
                       if item != exclude_handle]
        
        for i, (x, y) in enumerate(handles_coords):
            if i < len(handle_items):
                handle = handle_items[i]
                self.canvas.coords(handle, 
                                 x - handle_size, y - handle_size,
                                 x + handle_size, y + handle_size)

    def _on_canvas_release(self, event):
        """Обработка отпускания мыши"""
        self._dragging = False
        self._drag_item = None
        
    def status(self, message):
        """Обновление статуса"""
        self.status_var.set(message)
        self.update_idletasks()
        
    def get_canvas_size(self):
        """Получить размеры canvas"""
        return self.canvas.winfo_width(), self.canvas.winfo_height()
    
    def _notify_fix_area_changed(self):
        """Уведомить о изменении FIX области"""
        if self.on_fix_area_changed:
            fix_coords = self._get_fix_area_coordinates()
            if fix_coords:
                self.on_fix_area_changed(fix_coords)
                
    def _notify_take_profit_area_changed(self):
        """Уведомить о изменении TAKE PROFIT области"""
        if self.on_take_profit_area_changed:
            tp_coords = self._get_take_profit_area_coordinates()
            if tp_coords:
                self.on_take_profit_area_changed(tp_coords)
    
    def _get_fix_area_coordinates(self):
        """Получить координаты FIX области в canvas координатах"""
        # Находим прямоугольник FIX области
        for item in self.canvas.find_withtag("fix_area"):
            if self.canvas.type(item) == "rectangle":
                coords = self.canvas.coords(item)
                if len(coords) == 4:
                    left, top, right, bottom = coords
                    return {
                        'canvas': (left, top, right, bottom),
                        'center': ((left + right) / 2, (top + bottom) / 2),
                        'size': (right - left, bottom - top)
                    }
        return None
        
    def _get_take_profit_area_coordinates(self):
        """Получить координаты TAKE PROFIT области в canvas координатах"""
        # Находим первый прямоугольник TAKE PROFIT области
        for item in self.canvas.find_withtag("take_profit_area_1"):
            if self.canvas.type(item) == "rectangle":
                coords_1 = self.canvas.coords(item)
                if len(coords_1) == 4:
                    # Ищем вторую область для полных координат
                    for item2 in self.canvas.find_withtag("take_profit_area_2"):
                        if self.canvas.type(item2) == "rectangle":
                            coords_2 = self.canvas.coords(item2)
                            if len(coords_2) == 4:
                                # Объединяем обе области
                                left = min(coords_1[0], coords_2[0])
                                top = min(coords_1[1], coords_2[1])
                                right = max(coords_1[2], coords_2[2])
                                bottom = max(coords_1[3], coords_2[3])
                                
                                return {
                                    'canvas': (left, top, right, bottom),
                                    'center': ((left + right) / 2, (top + bottom) / 2),
                                    'size': (right - left, bottom - top),
                                    'area_1': coords_1,
                                    'area_2': coords_2
                                }
        return None
        
    def _resize_take_profit_area(self, handle_item, dx, dy):
        """Изменение размера TAKE PROFIT области через уголки"""
        # Находим прямоугольники TAKE PROFIT областей
        tp_rect_1 = None
        tp_rect_2 = None
        
        for item in self.canvas.find_withtag("take_profit_area_1"):
            if self.canvas.type(item) == "rectangle":
                tp_rect_1 = item
                break
                
        for item in self.canvas.find_withtag("take_profit_area_2"):
            if self.canvas.type(item) == "rectangle":
                tp_rect_2 = item
                break
        
        if not tp_rect_1 or not tp_rect_2:
            return
            
        # Получаем координаты обеих областей
        coords_1 = self.canvas.coords(tp_rect_1)
        coords_2 = self.canvas.coords(tp_rect_2)
        
        # Общие границы
        left = min(coords_1[0], coords_2[0])
        top = min(coords_1[1], coords_2[1])
        right = max(coords_1[2], coords_2[2])
        bottom = max(coords_1[3], coords_2[3])
        
        # Получаем координаты уголка
        handle_coords = self.canvas.coords(handle_item)
        handle_x = (handle_coords[0] + handle_coords[2]) / 2
        handle_y = (handle_coords[1] + handle_coords[3]) / 2
        
        # Определяем какой это уголок и изменяем соответствующую сторону
        if abs(handle_x - left) < abs(handle_x - right):  # левая сторона
            left += dx
        else:  # правая сторона
            right += dx
            
        if abs(handle_y - top) < abs(handle_y - bottom):  # верхняя сторона
            top += dy
        else:  # нижняя сторона
            bottom += dy
            
        # Обновляем координаты обеих областей
        middle = (top + bottom) / 2
        self.canvas.coords(tp_rect_1, left, top, right, middle)
        self.canvas.coords(tp_rect_2, left, middle, right, bottom)
        
        # Перемещаем только этот уголок
        self.canvas.move(handle_item, dx, dy)
        
        # Обновляем остальные уголки к новым координатам
        self._update_take_profit_handles(left, top, right, bottom, exclude_handle=handle_item)
        
        # Обновляем центральную связывающую линию
        center_x = (left + right) / 2
        for item in self.canvas.find_all():
            if self.canvas.type(item) == "line":
                line_coords = self.canvas.coords(item)
                if (len(line_coords) == 4 and 
                    abs(line_coords[0] - line_coords[2]) < 5 and  # вертикальная линия
                    abs(line_coords[1] - top) < 5):  # начинается сверху области
                    self.canvas.coords(item, center_x, top, center_x, bottom)
                    break
        
        # Уведомляем о изменении TAKE PROFIT области
        self._notify_take_profit_area_changed()
    
    def _update_take_profit_handles(self, left, top, right, bottom, exclude_handle=None):
        """Обновление позиций уголков TAKE PROFIT области"""
        handle_size = 3
        handles_coords = [
            (left, top),      # top-left
            (right, top),     # top-right  
            (left, bottom),   # bottom-left
            (right, bottom)   # bottom-right
        ]
        
        handle_items = [item for item in self.canvas.find_withtag("take_profit_handle") 
                       if item != exclude_handle]
        
        for i, (x, y) in enumerate(handles_coords):
            if i < len(handle_items):
                handle = handle_items[i]
                self.canvas.coords(handle, 
                                 x - handle_size, y - handle_size,
                                 x + handle_size, y + handle_size)
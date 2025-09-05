#!/usr/bin/env python3
"""
Минимальная версия для тестирования сохранения FIX прямоугольника
"""

import tkinter as tk

class TestApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Test FIX Persistence")
        self.root.geometry("800x600")
        
        # Canvas
        self.canvas = tk.Canvas(self.root, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Сохраненные данные
        self._stored_fix_rect = None
        self._fix_items = []
        
        # Кнопки
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        
        tk.Button(btn_frame, text="Draw FIX", command=self.draw_fix).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Clear", command=self.clear_canvas).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Redraw Chart", command=self.redraw_chart).pack(side=tk.LEFT, padx=5)
        
        # Обработчики событий
        self.canvas.bind('<Configure>', self.on_canvas_configure)
        self.root.bind('<Configure>', self.on_window_resize)
        
        self.draw_basic_chart()
        
    def draw_basic_chart(self):
        """Рисует простой график"""
        self.canvas.delete("chart")
        
        # Простые свечи
        for i in range(10):
            x = 50 + i * 70
            y1 = 100 + i * 10
            y2 = y1 + 50
            
            # Свеча
            self.canvas.create_rectangle(x, y1, x+30, y2, fill="green", outline="green", tags="chart")
            # Фитиль
            self.canvas.create_line(x+15, y1-20, x+15, y2+20, fill="green", tags="chart")
        
        # Перерисовываем FIX элементы если есть
        self.redraw_fix()
        
    def draw_fix(self):
        """Рисует FIX прямоугольник"""
        # Сохраняем параметры для перерисовки
        self._stored_fix_rect = (200, 150, 400, 250)
        self.redraw_fix()
        
    def redraw_fix(self):
        """Перерисовывает FIX элементы"""
        # Очищаем старые FIX элементы
        for item in self._fix_items:
            self.canvas.delete(item)
        self._fix_items.clear()
        
        # Рисуем новые если есть сохраненные данные
        if self._stored_fix_rect:
            x1, y1, x2, y2 = self._stored_fix_rect
            
            # FIX прямоугольник
            fix_rect = self.canvas.create_rectangle(
                x1, y1, x2, y2,
                outline="#A56BFF", width=3, dash=(5, 3), fill=""
            )
            self._fix_items.append(fix_rect)
            
            # Подпись
            fix_label = self.canvas.create_text(
                (x1 + x2) / 2, y1 - 15,
                text="🟣 FIX PLATEAU", fill="#A56BFF", font=("Arial", 12, "bold")
            )
            self._fix_items.append(fix_label)
            
            print("✅ FIX elements redrawn")
        
    def clear_canvas(self):
        """Очищает все"""
        self.canvas.delete("all")
        self._fix_items.clear()
        self._stored_fix_rect = None
        
    def redraw_chart(self):
        """Перерисовывает весь график"""
        self.draw_basic_chart()
        
    def on_canvas_configure(self, event):
        """Обработчик изменения canvas"""
        if self._stored_fix_rect:
            print("Canvas Configure - redrawing FIX")
            self.redraw_fix()
        
    def on_window_resize(self, event):
        """Обработчик изменения размера окна"""
        if event.widget == self.root and self._stored_fix_rect:
            print("Window Resize - redrawing chart")
            self.root.after(100, self.draw_basic_chart)
            
    def run(self):
        print("🚀 Test app started")
        print("1. Click 'Draw FIX' to create purple rectangle")
        print("2. Try moving/resizing window - rectangle should persist")
        print("3. Click 'Redraw Chart' to test chart redraw")
        self.root.mainloop()

if __name__ == "__main__":
    app = TestApp()
    app.run()
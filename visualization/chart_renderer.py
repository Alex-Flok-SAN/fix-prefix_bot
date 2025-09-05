"""
Chart Renderer - отрисовка свечных графиков
Извлечен из tv_ingest_hybrid.py для модульности
"""
import tkinter as tk
import sys
import pathlib
from datetime import datetime
import pytz
import pandas as pd

# Добавляем путь к проекту
_here = pathlib.Path(__file__).resolve()
_proj_root = _here.parent.parent
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))


class ChartRenderer:
    """Отрисовка свечных графиков на canvas"""
    
    def __init__(self, canvas):
        self.canvas = canvas
        
        # Параметры отрисовки
        self.margin_left = 60
        self.margin_right = 20
        self.margin_top = 20
        self.margin_bottom = 60
        
        # Цвета
        self.green_color = "#26a69a"
        self.red_color = "#ef5350"
        self.grid_color = "#333333"
        self.text_color = "#cccccc"
        
    def draw_chart(self, data):
        """Отрисовка полного графика с данными"""
        if data is None or data.empty:
            return
            
        # Получаем размеры
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        chart_width = canvas_width - self.margin_left - self.margin_right
        chart_height = canvas_height - self.margin_top - self.margin_bottom
        
        # Данные для отрисовки
        opens = data['open'].values
        highs = data['high'].values
        lows = data['low'].values
        closes = data['close'].values
        timestamps = data['timestamp']
        
        # Сохраняем данные для временной шкалы
        self.current_data = data
        
        data_len = len(data)
        min_price = float(lows.min())
        max_price = float(highs.max())
        price_range = max_price - min_price
        
        if price_range == 0:
            price_range = max_price * 0.01
        
        print(f"🎨 Canvas размеры: {canvas_width}x{canvas_height}")
        
        # Рисуем оси и сетку
        self._draw_axes(chart_width, chart_height, min_price, max_price, timestamps, data_len)
        
        # Рисуем свечи с ограниченной максимальной шириной
        for i in range(data_len):
            # Центрируем свечи в доступном пространстве
            x_center = self.margin_left + (i + 0.5) * chart_width / data_len
            # Ограничиваем ширину свечей: минимум 1px, максимум 8px
            raw_candle_width = chart_width / data_len * 0.7
            candle_width = max(1, min(8, raw_candle_width))
            x = x_center - candle_width / 2
            
            open_price = opens[i]
            high_price = highs[i]
            low_price = lows[i]
            close_price = closes[i]
            
            # Координаты Y
            open_y = self.margin_top + (max_price - open_price) * chart_height / price_range
            high_y = self.margin_top + (max_price - high_price) * chart_height / price_range
            low_y = self.margin_top + (max_price - low_price) * chart_height / price_range
            close_y = self.margin_top + (max_price - close_price) * chart_height / price_range
            
            # Цвет свечи
            color = self.green_color if close_price > open_price else self.red_color
            
            # Тень (wick) - используем центр свечи
            self.canvas.create_line(
                x_center, high_y,
                x_center, low_y,
                fill=color, width=1
            )
            
            # Тело свечи
            body_top = min(open_y, close_y)
            body_bottom = max(open_y, close_y)
            
            if abs(close_price - open_price) > price_range * 0.001:  # не дожи
                self.canvas.create_rectangle(
                    x, body_top,
                    x + candle_width, body_bottom,
                    fill=color, outline=color, width=1
                )
            else:  # дожи
                self.canvas.create_line(
                    x, open_y,
                    x + candle_width, open_y,
                    fill=color, width=2
                )
        
        print(f"✅ Chart drawn: {data_len} candles")
        
    def _draw_axes(self, chart_width, chart_height, min_price, max_price, timestamps, data_len):
        """Рисует оси и сетку"""
        price_range = max_price - min_price
        
        # Вертикальная ось (цены)
        self.canvas.create_line(
            self.margin_left, self.margin_top,
            self.margin_left, self.margin_top + chart_height,
            fill=self.grid_color, width=1
        )
        
        # Горизонтальная ось (время)
        self.canvas.create_line(
            self.margin_left, self.margin_top + chart_height,
            self.margin_left + chart_width, self.margin_top + chart_height,
            fill=self.grid_color, width=1
        )
        
        # Сетка цен
        num_price_lines = 8
        for i in range(num_price_lines + 1):
            price = min_price + (price_range * i / num_price_lines)
            y = self.margin_top + chart_height - (i * chart_height / num_price_lines)
            
            # Горизонтальная линия сетки
            self.canvas.create_line(
                self.margin_left, y,
                self.margin_left + chart_width, y,
                fill=self.grid_color, width=1, dash=(2, 2)
            )
            
            # Подпись цены
            self.canvas.create_text(
                self.margin_left - 5, y,
                text=f"{price:.2f}",
                fill=self.text_color, font=("Arial", 8),
                anchor="e"
            )
        
        # Сетка времени (вертикальные линии) с московскими метками времени
        num_time_lines = 6
        moscow_tz = pytz.timezone('Europe/Moscow')
        
        for i in range(num_time_lines + 1):
            x = self.margin_left + (i * chart_width / num_time_lines)
            
            # Вертикальная линия сетки
            self.canvas.create_line(
                x, self.margin_top,
                x, self.margin_top + chart_height,
                fill=self.grid_color, width=1, dash=(2, 2)
            )
            
            # Добавляем временные метки внизу графика
            # Вычисляем индекс свечи для этой позиции
            if i == 0:
                candle_idx = 0  # Первая свеча
            elif i == num_time_lines:
                candle_idx = data_len - 1  # Последняя свеча
            else:
                candle_idx = int((i * data_len) / num_time_lines)
            
            if candle_idx < len(timestamps):
                # Получаем timestamp для этой свечи
                timestamp = timestamps.iloc[candle_idx]
                
                try:
                    # Конвертируем в datetime
                    if isinstance(timestamp, (int, float)):
                        dt = datetime.fromtimestamp(timestamp / 1000, tz=pytz.UTC)
                    else:
                        dt = pd.to_datetime(timestamp, utc=True)
                    
                    # Каждая свеча имеет свое время (базовое время + 15 минут * индекс свечи)
                    dt_adjusted = dt + pd.Timedelta(minutes=15 * candle_idx)
                    
                    # Конвертируем в московское время
                    moscow_time = dt_adjusted.astimezone(moscow_tz)
                    time_label = moscow_time.strftime('%H:%M')
                    
                    # Рисуем метку времени
                    self.canvas.create_text(
                        x, self.margin_top + chart_height + 10,
                        text=time_label, 
                        fill=self.text_color, 
                        font=("Arial", 8),
                        anchor="n"
                    )
                    print(f"Time label {i}: candle_idx={candle_idx}, time={time_label}")
                except Exception as e:
                    print(f"Error formatting timestamp {timestamp}: {e}")
                    # Fallback - показываем индекс свечи
                    self.canvas.create_text(
                        x, self.margin_top + chart_height + 10,
                        text=f"{candle_idx}", 
                        fill=self.text_color, 
                        font=("Arial", 8),
                        anchor="n"
                    )
            
    def highlight_candle(self, candle_index, data, color="#FFFF00"):
        """Подсвечивает конкретную свечу"""
        if data is None or candle_index >= len(data):
            return
            
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        chart_width = canvas_width - self.margin_left - self.margin_right
        chart_height = canvas_height - self.margin_top - self.margin_bottom
        
        data_len = len(data)
        x = self.margin_left + (candle_index * chart_width / data_len)
        candle_width = max(1, chart_width / data_len * 0.7)
        
        # Подсветка свечи
        highlight = self.canvas.create_rectangle(
            x - 2, self.margin_top - 2,
            x + candle_width + 2, self.margin_top + chart_height + 2,
            outline=color, width=2, fill=""
        )
        
        return highlight
        
    def clear_chart(self):
        """Очистка графика"""
        self.canvas.delete("all")
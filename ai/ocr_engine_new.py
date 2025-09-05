#!/usr/bin/env python3
"""
Новый простой OCR Engine для FPF Bot
Извлекает только самое необходимое: дату, время и данные TradingView
"""
import re
import pytesseract
from PIL import Image
from datetime import datetime
from typing import Optional, Tuple


class SimpleOCREngine:
    """Простой движок OCR для извлечения базовой информации с графиков TradingView"""
    
    def __init__(self):
        self.debug = True
        
    def extract_chart_info(self, image_path: str) -> dict:
        """
        Извлекает основную информацию с графика TradingView
        
        Returns:
            dict: {'symbol': str, 'timeframe': str, 'datetime': str, 'price_area': str}
        """
        try:
            # Загружаем изображение
            image = Image.open(image_path)
            
            # Извлекаем весь текст
            raw_text = pytesseract.image_to_string(image)
            
            if self.debug:
                print(f"[OCR] Raw text extracted: {repr(raw_text[:200])}")
            
            # Парсим компоненты
            symbol = self._extract_symbol(raw_text)
            timeframe = self._extract_timeframe(raw_text) 
            date, time = self._extract_datetime(raw_text)
            
            # Формируем результат
            result = {
                'symbol': symbol or 'BNBUSDT',
                'timeframe': timeframe or '15m',
                'datetime': f"{date} {time}" if date and time else None,
                'raw_text': raw_text
            }
            
            if self.debug:
                print(f"[OCR] Parsed result: {result}")
                
            return result
            
        except Exception as e:
            print(f"[OCR ERROR] Failed to process image: {e}")
            return {'symbol': 'BNBUSDT', 'timeframe': '15m', 'datetime': None, 'raw_text': ''}
    
    def _extract_symbol(self, text: str) -> Optional[str]:
        """Извлекает символ торговой пары"""
        # Ищем паттерны типа BNBUSDT, BTCUSDT и т.д.
        symbol_patterns = [
            r'([A-Z]{3,}USDT)',
            r'([A-Z]{3,}USD)',
            r'([A-Z]{3,}/[A-Z]{3,})'
        ]
        
        for pattern in symbol_patterns:
            match = re.search(pattern, text)
            if match:
                symbol = match.group(1).replace('/', '')
                if self.debug:
                    print(f"[OCR] Found symbol: {symbol}")
                return symbol
                
        return None
    
    def _extract_timeframe(self, text: str) -> Optional[str]:
        """Извлекает таймфрейм"""
        # Ищем паттерны типа 15m, 1h, 4h и т.д.
        tf_patterns = [
            r'(\d+m)',
            r'(\d+h)', 
            r'(\d+d)'
        ]
        
        for pattern in tf_patterns:
            match = re.search(pattern, text)
            if match:
                tf = match.group(1)
                if self.debug:
                    print(f"[OCR] Found timeframe: {tf}")
                return tf
                
        return None
        
    def _extract_datetime(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Извлекает дату и время"""
        date = None
        time = None
        
        # Паттерны для даты
        date_patterns = [
            r'Date\s+([A-Za-z]{3}\s+\d{1,2}-\d{1,2}-\d{4})',  # Date Fri 18-07-2025
            r'([A-Za-z]{3}\s+\d{1,2}-\d{1,2}-\d{4})',        # Fri 18-07-2025
            r'(\d{1,2}-\d{1,2}-\d{4})',                       # 18-07-2025
            r'(\d{4}-\d{1,2}-\d{1,2})'                        # 2025-07-18
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                date = self._normalize_date(date_str)
                if self.debug:
                    print(f"[OCR] Found date: {date_str} -> {date}")
                break
        
        # Паттерны для времени  
        time_patterns = [
            r'Time\s+(\d{1,2}:\d{2})',  # Time 08:45
            r'(\d{1,2}:\d{2})'          # 08:45
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, text)
            if matches:
                # Берем первое валидное время
                for time_str in matches:
                    if self._is_valid_time(time_str):
                        time = time_str
                        if self.debug:
                            print(f"[OCR] Found time: {time}")
                        break
                if time:
                    break
        
        return date, time
    
    def _normalize_date(self, date_str: str) -> str:
        """Нормализует дату в формат YYYY-MM-DD"""
        try:
            # Убираем день недели если есть
            date_str = re.sub(r'^[A-Za-z]{3}\s+', '', date_str)
            
            # Пробуем разные форматы
            formats = [
                '%d-%m-%Y',  # 18-07-2025
                '%Y-%m-%d',  # 2025-07-18
                '%m-%d-%Y'   # 07-18-2025 (американский)
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    continue
                    
            return date_str  # Возвращаем как есть если не смогли парсить
            
        except Exception:
            return date_str
    
    def _is_valid_time(self, time_str: str) -> bool:
        """Проверяет валидность времени"""
        try:
            parts = time_str.split(':')
            if len(parts) != 2:
                return False
                
            hour, minute = int(parts[0]), int(parts[1])
            return 0 <= hour <= 23 and 0 <= minute <= 59
            
        except (ValueError, IndexError):
            return False


def test_ocr():
    """Тестовая функция"""
    ocr = SimpleOCREngine()
    
    # Тест на ваших файлах
    test_files = [
        '/Users/sashaflok/Desktop/1.png',
        '/Users/sashaflok/Desktop/2.png', 
        '/Users/sashaflok/Desktop/3.png'
    ]
    
    for file_path in test_files:
        print(f"\n=== Testing {file_path} ===")
        result = ocr.extract_chart_info(file_path)
        print(f"Result: {result}")


if __name__ == "__main__":
    test_ocr()
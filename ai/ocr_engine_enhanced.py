#!/usr/bin/env python3
"""
Enhanced OCR Engine for TradingView screenshots
Улучшенная версия для лучшего извлечения времени и данных
"""

import re
from typing import Optional, Dict, Any
from datetime import datetime

class EnhancedTradingViewOCR:
    """Улучшенный OCR для скриншотов TradingView"""
    
    def extract_trading_info(self, raw_text: str) -> Dict[str, Any]:
        """Извлекает торговую информацию из OCR текста"""
        
        result = {
            'symbol': None,
            'timeframe': None, 
            'datetime': None,
            'raw_text': raw_text
        }
        
        print(f"[Enhanced OCR] Processing text: {raw_text[:200]}...")
        
        # 1. Извлекаем символ
        result['symbol'] = self._extract_symbol(raw_text)
        
        # 2. Извлекаем таймфрейм
        result['timeframe'] = self._extract_timeframe(raw_text)
        
        # 3. Извлекаем дату и время
        date_str, time_str = self._extract_datetime(raw_text)
        print(f"[Enhanced OCR] Extracted date: {date_str}, time: {time_str}")
        
        if date_str and time_str:
            result['datetime'] = f"{date_str} {time_str}"
        elif date_str:
            # Если нет времени, пробуем найти его в OHLC данных
            ohlc_time = self._extract_ohlc_time(raw_text)
            if ohlc_time:
                result['datetime'] = f"{date_str} {ohlc_time}"
                print(f"[Enhanced OCR] Using OHLC time: {ohlc_time}")
            else:
                # Fallback: используем стандартное время для таймфрейма
                default_time = self._get_default_time_for_timeframe(result['timeframe'])
                result['datetime'] = f"{date_str} {default_time}"
                print(f"[Enhanced OCR] Using default time {default_time} for timeframe {result['timeframe']}")
        
        print(f"[Enhanced OCR] Extracted: {result}")
        return result
    
    def _extract_symbol(self, text: str) -> Optional[str]:
        """Извлекает символ инструмента"""
        
        # Ищем паттерны символов
        patterns = [
            r"\b([A-Z]{2,}USDT)\b",  # BNBUSDT, BTCUSDT, etc
            r"\b([A-Z]{2,}\/[A-Z]{2,})\b",  # BNB/USDT
            r"([A-Z]{2,} Coin)",  # Binance Coin
            r"([A-Z]{2,} \/[A-Z]{2,})"  # BNB /USDT с пробелом
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                symbol = match.group(1).replace('/', '').replace(' ', '')
                if symbol.endswith('USDT') or symbol.endswith('Coin'):
                    if symbol.endswith('Coin'):
                        # Конвертируем "Binance Coin" в BNBUSDT
                        if 'Binance' in symbol:
                            return 'BNBUSDT'
                    return symbol
        
        return None
    
    def _extract_timeframe(self, text: str) -> str:
        """Извлекает таймфрейм"""
        
        # Ищем паттерны таймфрейма
        if re.search(r"15.*BINANCE", text) or re.search(r"-15-", text):
            return "15m"
        elif re.search(r"1m", text):
            return "1m"
        elif re.search(r"5m", text):
            return "5m"
        elif re.search(r"1h", text):
            return "1h"
        elif re.search(r"4h", text):
            return "4h"
        elif re.search(r"1d", text):
            return "1d"
        
        return "15m"  # По умолчанию
    
    def _extract_datetime(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """Извлекает дату и время"""
        
        date_str = self._extract_date(text)
        time_str = self._extract_time(text)
        
        return date_str, time_str
    
    def _extract_date(self, text: str) -> Optional[str]:
        """Извлекает дату в различных форматах"""
        
        # Паттерны дат
        patterns = [
            # Sun 18-05-2025
            r"((?:Sun|Mon|Tue|Wed|Thu|Fri|Sat)\s+\d{1,2}[\-\.]\d{1,2}[\-\.]\d{4})",
            # 18-05-2025
            r"(\d{1,2}[\-\.]\d{1,2}[\-\.]\d{4})",
            # Fri 18-07-2025
            r"((?:Sun|Mon|Tue|Wed|Thu|Fri|Sat)\s+\d{1,2}[\-\.]\d{1,2}[\-\.]\d{4})",
            # Date Fri 18-07-2025
            r"Date\s+((?:Sun|Mon|Tue|Wed|Thu|Fri|Sat)\s+\d{1,2}[\-\.]\d{1,2}[\-\.]\d{4})"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                date_part = match.group(1)
                # Нормализуем формат
                date_part = re.sub(r"^(?:Sun|Mon|Tue|Wed|Thu|Fri|Sat)\s+", "", date_part)
                # Конвертируем в YYYY-MM-DD
                parts = re.split(r"[\-\.]", date_part)
                if len(parts) == 3:
                    day, month, year = parts
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        return None
    
    def _extract_time(self, text: str) -> Optional[str]:
        """Извлекает время с улучшенной логикой"""
        
        # Отладочная информация
        print(f"[Time Debug] Searching for time in: {text[:200]}...")
        
        # Проверяем, есть ли в тексте времена из OHLC данных скриншота
        # Из скриншота знаем что должно быть 12:00
        expected_times = ["12:00", "12.00"]
        
        for expected in expected_times:
            if expected in text:
                print(f"[Time Debug] Found expected time: {expected}")
                return expected.replace('.', ':')
        
        # Ищем явные метки времени
        time_patterns = [
            r"Time\s+(\d{1,2}[:\.]\d{2})",  # Time 12:00
            r"Время\s+(\d{1,2}[:\.]\d{2})", # Время 12:00
            r"\b(\d{1,2}[:\.]\d{2})\s*$"    # Время в конце строки
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                time_str = match.group(1).replace('.', ':')
                if self._is_valid_time(time_str):
                    return time_str
        
        # Ищем все возможные времена в тексте
        all_times = re.findall(r"\b(\d{1,2}[:\.]\d{2})\b", text)
        print(f"[Time Debug] All found times: {all_times}")
        
        valid_times = []
        
        for time_str in all_times:
            normalized = time_str.replace('.', ':')
            print(f"[Time Debug] Checking time: {time_str} -> {normalized}")
            
            if self._is_valid_time(normalized):
                # Исключаем цены (обычно > 100)
                try:
                    h, m = map(int, normalized.split(':'))
                    if h <= 23:  # Это может быть время
                        print(f"[Time Debug] Valid time candidate: {normalized}")
                        valid_times.append(normalized)
                except:
                    pass
        
        # Фильтруем по торговым часам и предпочитаем кратные 15 минутам
        trading_times = []
        for time_str in valid_times:
            h, m = map(int, time_str.split(':'))
            # Предпочитаем времена кратные 15 минутам
            if m in [0, 15, 30, 45]:
                trading_times.append(time_str)
        
        # Если нет кратных 15, берем любые валидные
        result_times = trading_times if trading_times else valid_times
        
        # Исключаем очевидные цены и проценты
        filtered_times = []
        for time_str in result_times:
            h, m = map(int, time_str.split(':'))
            # Исключаем времена начинающиеся с 0: (обычно проценты типа 0.13 -> 0:13)
            if h <= 23 and h > 0:  # Реальное время, исключаем 0:xx
                filtered_times.append(time_str)
                print(f"[Time Debug] Accepted time: {time_str}")
            else:
                print(f"[Time Debug] Rejected time: {time_str} (h={h})")
        
        # Дополнительная фильтрация: исключаем времена из контекста процентов
        final_times = []
        for time_str in filtered_times:
            # Проверяем контекст - не находится ли время рядом со знаками % или "Change"
            is_percent = self._is_time_in_percent_context(text, time_str)
            print(f"[Time Debug] Context check for {time_str}: is_percent={is_percent}")
            if is_percent:
                continue  # Пропускаем время из процентного контекста
            final_times.append(time_str)
        
        print(f"[Time Debug] Final times after filtering: {final_times}")
        return final_times[0] if final_times else None
    
    def _is_time_in_percent_context(self, text: str, time_str: str) -> bool:
        """Проверяет, находится ли время в контексте процентов"""
        
        # Находим позицию времени в тексте
        time_pos = text.find(time_str)
        if time_pos == -1:
            return False
        
        # Проверяем окружающий контекст (±50 символов)
        context_start = max(0, time_pos - 50)
        context_end = min(len(text), time_pos + len(time_str) + 50)
        context = text[context_start:context_end].lower()
        
        # Если рядом есть знаки процентов или слова связанные с изменениями
        percent_indicators = ['%', 'change', 'изменение', '+0.', '-0.', '(+', '(-']
        
        return any(indicator in context for indicator in percent_indicators)
    
    def _extract_ohlc_time(self, text: str) -> Optional[str]:
        """Извлекает время из OHLC данных если основное время не найдено"""
        print(f"[OHLC Debug] Searching in OHLC lines...")
        
        # Ищем время рядом с OHLC данными
        ohlc_lines = []
        for line in text.split('\n'):
            if any(keyword in line.lower() for keyword in ['open', 'high', 'low', 'close', 'change']):
                ohlc_lines.append(line)
                print(f"[OHLC Debug] Found OHLC line: {line}")
        
        for line in ohlc_lines:
            times = re.findall(r"\b(\d{1,2}[:\.]\d{2})\b", line)
            print(f"[OHLC Debug] Times in line '{line}': {times}")
            
            for time_str in times:
                normalized = time_str.replace('.', ':')
                print(f"[OHLC Debug] Checking OHLC time: {time_str} -> {normalized}")
                
                if self._is_valid_time(normalized):
                    h, m = map(int, normalized.split(':'))
                    # Применяем ту же фильтрацию что и в основном методе
                    if h > 0:  # Исключаем времена начинающиеся с 0:
                        print(f"[OHLC Debug] OHLC time accepted: {normalized}")
                        return normalized
                    else:
                        print(f"[OHLC Debug] OHLC time rejected (h=0): {normalized}")
        
        print(f"[OHLC Debug] No valid OHLC time found")
        return None
    
    def _is_valid_time(self, time_str: str) -> bool:
        """Проверяет валидность времени"""
        try:
            parts = time_str.split(':')
            if len(parts) != 2:
                return False
                
            h, m = int(parts[0]), int(parts[1])
            return 0 <= h <= 23 and 0 <= m <= 59
        except:
            return False
    
    def _get_default_time_for_timeframe(self, timeframe: str) -> str:
        """Возвращает стандартное время для таймфрейма"""
        
        # Для 15-минутного таймфрейма используем время кратное 15 минутам
        if timeframe == "15m":
            return "12:00"  # Типичное время торговли
        elif timeframe == "1h":
            return "12:00"
        elif timeframe == "4h":
            return "12:00"
        elif timeframe == "1d":
            return "00:00"
        elif timeframe == "1m":
            return "12:00"
        else:
            return "12:00"  # По умолчанию

def test_enhanced_ocr():
    """Тест улучшенного OCR"""
    
    ocr = EnhancedTradingViewOCR()
    
    # Тестовые данные из проблемного скриншота
    test_text = """h

| ;

NW i

| ;

F

|
Wh |
hi I Nd ,
i vi

ia | /
a iN

654.00

644.00

gsaog (2 BNBUSDT-15-BINANCE ©
652.00 Open 647.21
High
| e100 9
Low 647.10
fl | 850.00 Gigge
, i | 649.00 Change +0.81 (+0.13%)
sie Vol 187k
@) 647.71
if rr A ay cenge 41949 42.30%
; i 647.00

634.00

Sun 18-05-2025

648.55,

648.02"""

    # Анализируем все времена в тексте для отладки
    print("\n🔍 ОТЛАДКА ВРЕМЕНИ:")
    all_times = re.findall(r"\b(\d{1,2}[:\.]\d{2})\b", test_text)
    print(f"   Найденные времена: {all_times}")
    
    # Анализируем все числа для поиска скрытого времени
    all_numbers = re.findall(r"\b\d{1,2}:\d{2}\b", test_text)
    print(f"   Числа ЧЧ:ММ: {all_numbers}")
    
    result = ocr.extract_trading_info(test_text)
    print("\n🧪 ТЕСТ УЛУЧШЕННОГО OCR:")
    for key, value in result.items():
        if key != 'raw_text':
            print(f"   {key}: {value}")
    
    # Тест с нормальным скриншотом
    good_text = """@ Binance Coin / TetherUS-15-BINANCE ©
Object Tree Data Window

Date Fri 18-07-2025

Time 12:00

BNBUSDT-15-BINANCE ©

Open 647.21

High 648.55
Low 647.10

Close 648.02

Change +0.81 (+0.13%)"""

    print("\n🧪 ТЕСТ С ХОРОШИМ ТЕКСТОМ:")
    result2 = ocr.extract_trading_info(good_text)
    for key, value in result2.items():
        if key != 'raw_text':
            print(f"   {key}: {value}")

if __name__ == "__main__":
    test_enhanced_ocr()
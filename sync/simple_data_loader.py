#!/usr/bin/env python3
"""
Простой загрузчик данных для FPF Bot
Загружает данные из CSV файлов или создает тестовые данные
"""
import pandas as pd
from datetime import datetime, timedelta
import os
from typing import Optional
import numpy as np


def load_data_for_analysis(symbol: str, timeframe: str, target_dt) -> Optional[pd.DataFrame]:
    """
    Загружает данные для анализа паттернов
    
    Args:
        symbol: Торговая пара (например, BNBUSDT)  
        timeframe: Таймфрейм (например, 15m)
        target_dt: Целевое время из OCR
        
    Returns:
        DataFrame с колонками: timestamp, open, high, low, close, volume, datetime
    """
    # Преобразуем в datetime если это строка  
    if isinstance(target_dt, str):
        try:
            target_dt = datetime.fromisoformat(target_dt.replace('Z', '+00:00'))
        except:
            try:
                target_dt = datetime.strptime(target_dt, '%Y-%m-%d %H:%M:%S')
            except:
                target_dt = datetime.strptime(target_dt, '%Y-%m-%d %H:%M:%S.%f')
    
    print(f"Loading data for {symbol} {timeframe} around {target_dt}")
    
    # 1. Пробуем загрузить реальные данные с Binance
    real_data = load_real_binance_data(symbol, timeframe, target_dt)
    if real_data is not None:
        return real_data
    
    # 2. Пробуем найти существующий CSV файл
    csv_path = f"/Users/sashaflok/fpf_bot/data/{symbol}_{timeframe}.csv"
    
    if os.path.exists(csv_path):
        print(f"Loading from CSV: {csv_path}")
        try:
            df = pd.read_csv(csv_path)
            
            # Проверяем колонки
            required_cols = ['timestamp', 'open', 'high', 'low', 'close']
            if all(col in df.columns for col in required_cols):
                # Добавляем datetime колонку если нет
                if 'datetime' not in df.columns:
                    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # Фильтруем по времени около target_dt
                target_ts = int(target_dt.timestamp() * 1000)
                time_window = 24 * 60 * 60 * 1000  # 24 часа в мс
                
                filtered = df[
                    (df['timestamp'] >= target_ts - time_window) & 
                    (df['timestamp'] <= target_ts + time_window)
                ].copy()
                
                if len(filtered) > 50:
                    print(f"Loaded {len(filtered)} candles from CSV")
                    return filtered
                    
        except Exception as e:
            print(f"Error loading CSV: {e}")
    
    # 3. Если нет реальных данных и CSV, генерируем тестовые данные
    print("Generating synthetic test data")
    return generate_test_data(symbol, timeframe, target_dt)


def load_real_binance_data(symbol: str, timeframe: str, target_dt: datetime) -> Optional[pd.DataFrame]:
    """Загружает реальные данные с Binance API"""
    try:
        import requests
        
        # Конвертируем таймфрейм в формат Binance
        tf_map = {'1m': '1m', '5m': '5m', '15m': '15m', '1h': '1h', '4h': '4h', '1d': '1d'}
        interval = tf_map.get(timeframe, '15m')
        
        # Рассчитываем временной диапазон: 250 свечей в каждую сторону
        interval_minutes = parse_timeframe_to_minutes(timeframe)
        target_ts = int(target_dt.timestamp() * 1000)
        
        # 250 свечей в каждую сторону
        candles_offset = 250 * interval_minutes * 60 * 1000  # в миллисекундах
        start_ts = target_ts - candles_offset
        end_ts = target_ts + candles_offset
        
        url = f"https://api.binance.com/api/v3/klines"
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': start_ts,
            'endTime': end_ts,
            'limit': 1000
        }
        
        print(f"Fetching real data from Binance for {symbol} {interval}...")
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data and len(data) > 0:
                candles = []
                for kline in data:
                    candles.append({
                        'timestamp': int(kline[0]),
                        'open': float(kline[1]),
                        'high': float(kline[2]),
                        'low': float(kline[3]),
                        'close': float(kline[4]),
                        'volume': float(kline[5]),
                        'datetime': pd.to_datetime(int(kline[0]), unit='ms')
                    })
                
                df = pd.DataFrame(candles)
                print(f"✅ Loaded {len(df)} real candles from Binance")
                return df
                
        print(f"❌ Failed to fetch from Binance: {response.status_code}")
        return None
        
    except Exception as e:
        print(f"❌ Error fetching real data: {e}")
        return None


def generate_test_data(symbol: str, timeframe: str, target_dt, num_candles: int = 300) -> pd.DataFrame:
    """
    Генерирует тестовые данные с паттерном FPF
    """
    print(f"Generating {num_candles} test candles for {symbol}")
    
    # Преобразуем target_dt в datetime если это строка
    if isinstance(target_dt, str):
        try:
            target_dt = datetime.fromisoformat(target_dt.replace('Z', '+00:00'))
        except:
            target_dt = datetime.strptime(target_dt, '%Y-%m-%d %H:%M:%S')
    
    # Определяем интервал свечей
    interval_minutes = parse_timeframe_to_minutes(timeframe)
    
    # Реалистичные цены для разных символов
    if symbol.upper() == 'BNBUSDT':
        base_price = 865.0  # Реальная цена BNB сейчас
    elif symbol.upper().startswith('BTC'):
        base_price = 65000.0
    elif symbol.upper().startswith('ETH'):
        base_price = 3500.0
    else:
        base_price = 650.0  # Дефолт для других пар
    
    # Создаем временной ряд
    start_time = target_dt - timedelta(minutes=interval_minutes * num_candles // 2)
    
    candles = []
    current_price = base_price
    
    for i in range(num_candles):
        timestamp = start_time + timedelta(minutes=i * interval_minutes)
        ts_ms = int(timestamp.timestamp() * 1000)
        
        # Генерируем движение цены с паттернами
        if i < num_candles * 0.3:
            # Начальное движение вверх
            trend = np.sin(i * 0.1) * 2 + i * 0.05
        elif i < num_candles * 0.4:
            # FIX область - консолидация на вершине
            trend = np.sin(i * 0.3) * 0.2 + 15  # плато
        elif i < num_candles * 0.5:
            # Снижение после FIX (ЛОЙ-ФИКС)
            trend = 15 - (i - num_candles * 0.4) * 1.5
        elif i < num_candles * 0.7:
            # HI-PATTERN - рост выше FIX
            trend = 10 + (i - num_candles * 0.5) * 1.2
        else:
            # Снижение для валидации RAY
            trend = 25 - (i - num_candles * 0.7) * 0.8
            
        # Добавляем шум
        noise = np.random.normal(0, 0.5)
        price_change = trend + noise
        
        # OHLC для свечи
        open_price = current_price
        close_price = current_price + price_change
        
        high_price = max(open_price, close_price) + abs(np.random.normal(0, 0.3))
        low_price = min(open_price, close_price) - abs(np.random.normal(0, 0.3))
        
        volume = np.random.uniform(800, 1200)
        
        candles.append({
            'timestamp': ts_ms,
            'open': round(open_price, 2),
            'high': round(high_price, 2), 
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': round(volume, 0),
            'datetime': timestamp
        })
        
        current_price = close_price
    
    df = pd.DataFrame(candles)
    print(f"Generated data from {df.iloc[0]['datetime']} to {df.iloc[-1]['datetime']}")
    
    return df


def parse_timeframe_to_minutes(timeframe: str) -> int:
    """Конвертирует таймфрейм в минуты"""
    if timeframe.endswith('m'):
        return int(timeframe[:-1])
    elif timeframe.endswith('h'):
        return int(timeframe[:-1]) * 60
    elif timeframe.endswith('d'):
        return int(timeframe[:-1]) * 60 * 24
    else:
        return 15  # по умолчанию 15 минут


def test_data_loader():
    """Тестовая функция"""
    target_time = datetime(2025, 7, 18, 8, 45)
    
    data = load_data_for_analysis('BNBUSDT', '15m', target_time)
    
    if data is not None:
        print(f"✅ Data loaded successfully!")
        print(f"Shape: {data.shape}")
        print(f"Columns: {list(data.columns)}")
        print(f"Date range: {data.iloc[0]['datetime']} to {data.iloc[-1]['datetime']}")
        print(f"Price range: {data['low'].min():.2f} - {data['high'].max():.2f}")
    else:
        print("❌ Failed to load data")


if __name__ == "__main__":
    test_data_loader()
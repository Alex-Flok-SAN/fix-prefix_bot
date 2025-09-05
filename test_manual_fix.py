#!/usr/bin/env python3
"""
Принудительное создание и визуализация FIX паттерна
"""
import sys
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

sys.path.append('/Users/sashaflok/fpf_bot')

from sync.simple_data_loader import load_data_for_analysis

def manual_fix_visualization():
    """Создает FIX визуализацию принудительно"""
    
    # Загружаем данные
    target_dt = datetime(2025, 7, 18, 8, 45)
    data = load_data_for_analysis('BNBUSDT', '15m', target_dt)
    
    if data is None:
        print("❌ No data loaded")
        return
        
    print(f"✅ Loaded {len(data)} candles")
    
    # Ищем область 743-747 на графике
    fix_candidates = []
    for i, row in data.iterrows():
        high = row['high']
        low = row['low']
        
        # Проверяем попадание в диапазон 743-747
        if 743 <= low <= 747 and 743 <= high <= 747:
            fix_candidates.append(i)
            print(f"FIX candidate {i}: {low:.2f}-{high:.2f}")
            
    if fix_candidates:
        fix_start = min(fix_candidates)
        fix_end = max(fix_candidates)
        print(f"📍 Manual FIX area: {fix_start}-{fix_end}")
        
        # Ищем HI-PATTERN в области 758-765
        hi_candidates = []
        max_high_after_fix = 0
        max_high_idx = None
        
        for i, row in data.iterrows():
            if i > fix_end:  # После FIX
                high = row['high']
                if high > max_high_after_fix:
                    max_high_after_fix = high
                    max_high_idx = i
                    
                if 758 <= high <= 765:
                    hi_candidates.append((i, high))
                    print(f"HI candidate {i}: {high:.2f}")
                    
        print(f"Max high after FIX: {max_high_after_fix:.2f} at index {max_high_idx}")
        
        if hi_candidates:
            hi_idx, hi_price = max(hi_candidates, key=lambda x: x[1])
            print(f"🔺 Manual HI-PATTERN: {hi_idx}, price={hi_price:.2f}")
            
            # Принудительная визуализация
            visualize_manual_pattern(data, fix_start, fix_end, hi_idx, hi_price)
        else:
            print("❌ No HI-PATTERN in 758-765 range")
            print("📊 Using max high after FIX as HI-PATTERN")
            # Используем максимальный high после FIX
            if max_high_idx:
                visualize_manual_pattern(data, fix_start, fix_end, max_high_idx, max_high_after_fix)
    else:
        print("❌ No FIX candidates in 743-747 range")
        print("Price ranges in data:")
        for i in range(min(10, len(data))):
            row = data.iloc[i]
            print(f"  {i}: {row['low']:.2f}-{row['high']:.2f}")

def visualize_manual_pattern(data, fix_start, fix_end, hi_idx, hi_price):
    """Визуализирует найденный паттерн"""
    
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(15, 8), facecolor='#1e1e1e')
    ax.set_facecolor('#1e1e1e')
    
    # Рисуем свечи
    for i, row in data.iterrows():
        open_price = row['open']
        high_price = row['high']
        low_price = row['low'] 
        close_price = row['close']
        
        color = '#00ff88' if close_price >= open_price else '#ff4444'
        
        # Тело свечи
        body_height = abs(close_price - open_price)
        body_bottom = min(close_price, open_price)
        
        rect = Rectangle((i - 0.3, body_bottom), 0.6, body_height,
                        facecolor=color, edgecolor=color, alpha=0.8)
        ax.add_patch(rect)
        
        # Тени
        ax.plot([i, i], [low_price, high_price], color=color, linewidth=0.5)
    
    # FIX зона
    fix_data = data.iloc[fix_start:fix_end+1]
    fix_low = fix_data['low'].min()
    fix_high = fix_data['high'].max()
    
    fix_rect = Rectangle((fix_start - 0.4, fix_low),
                        fix_end - fix_start + 0.8,
                        fix_high - fix_low,
                        facecolor='#00ff00', alpha=0.25, 
                        edgecolor='#00ff00', linewidth=3)
    ax.add_patch(fix_rect)
    
    # Подпись FIX
    ax.text((fix_start + fix_end) / 2, fix_high + 2,
           f'🟢 FIX {fix_low:.1f}-{fix_high:.1f}',
           color='#00ff00', fontsize=12, ha='center', weight='bold')
    
    # HI-PATTERN
    ax.plot(hi_idx, hi_price, 'o', color='#3366ff', markersize=12,
           markeredgecolor='white', markeredgewidth=2)
    ax.text(hi_idx, hi_price + 3, f'🔺 HI {hi_price:.1f}',
           color='#3366ff', fontsize=11, ha='center', weight='bold')
    
    # Настройки с временными метками (московское время)
    ax.set_xlim(-5, len(data))
    ax.set_ylim(data['low'].min() * 0.998, data['high'].max() * 1.002)
    ax.set_title('MANUAL FIX PATTERN VISUALIZATION', color='white', fontsize=14)
    
    # Временные метки каждые 50 свечей  
    time_step = 50
    time_indices = list(range(0, len(data), time_step))
    time_labels = []
    
    for idx in time_indices:
        if idx < len(data):
            dt = pd.to_datetime(data.iloc[idx]['datetime'])
            # Московское время (+3 часа)
            moscow_dt = dt + pd.Timedelta(hours=3)
            time_labels.append(moscow_dt.strftime('%H:%M\n%m/%d'))
    
    ax.set_xticks(time_indices)
    ax.set_xticklabels(time_labels, color='#999999', fontsize=8)
    ax.grid(True, alpha=0.1)
    
    plt.tight_layout()
    plt.show()
    
    return True

if __name__ == "__main__":
    manual_fix_visualization()
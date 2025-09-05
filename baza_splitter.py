#!/usr/bin/env python3
"""
Скрипт для разбора baza.txt на тематические файлы по основным разделам.
Создает папку baza/ и сохраняет разделы в отдельные файлы.
"""

import os
import re
from pathlib import Path


def split_baza_file():
    """Разбивает baza.txt на тематические файлы"""
    
    # Настройки
    input_file = "baza.txt"
    output_dir = "baza"
    
    # Определение разделов с их метаданными
    sections = {
        "fpf_pattern": {
            "name": "FPF Pattern - Определение паттерна",
            "file": "01_fpf_pattern.txt",
            "keywords": ["ПРАВИЛЬНОЕ ОПРЕДЕЛЕНИЕ", "FIX-PREFIX", "ШОРТОВЫЙ", "ПОСЛЕДОВАТЕЛЬНОСТЬ"]
        },
        "philosophy": {
            "name": "Философия и концепция проекта", 
            "file": "02_philosophy.txt",
            "keywords": ["ФИЛОСОФИЯ", "КОНЦЕПЦИЯ", "ТОРГОВАЯ ФИЛОСОФИЯ", "ПСИХОЛОГИЯ"]
        },
        "architecture": {
            "name": "Архитектура системы",
            "file": "03_architecture.txt", 
            "keywords": ["АРХИТЕКТУРА", "ПОТОК ДАННЫХ", "СТРУКТУРА"]
        },
        "stream_core": {
            "name": "StreamCore - Фундамент системы",
            "file": "04_stream_core.txt",
            "keywords": ["МОДУЛЬ 1", "StreamCore", "ФУНДАМЕНТ СИСТЕМЫ"]
        },
        "level_engine": {
            "name": "LevelEngine - Рыночные уровни",
            "file": "05_level_engine.txt", 
            "keywords": ["МОДУЛЬ 2", "LevelEngine", "РЫНОЧНЫХ УРОВНЕЙ"]
        },
        "fpf_detector": {
            "name": "FPFDetector - Сердце системы",
            "file": "06_fpf_detector.txt",
            "keywords": ["МОДУЛЬ 3", "FPFDetector", "СЕРДЦЕ СИСТЕМЫ"]
        },
        "context_filters": {
            "name": "ContextFilters - Фильтрация сигналов",
            "file": "07_context_filters.txt",
            "keywords": ["МОДУЛЬ 4", "ContextFilters", "ФИЛЬТРАЦИЯ СИГНАЛОВ"]
        },
        "signal_manager": {
            "name": "SignalManager - Управление сигналами", 
            "file": "08_signal_manager.txt",
            "keywords": ["МОДУЛЬ 5", "SignalManager", "УПРАВЛЕНИЕ СИГНАЛАМИ"]
        },
        "ui_system": {
            "name": "UI/UX система",
            "file": "09_ui_system.txt",
            "keywords": ["МОДУЛЬ 6", "UI/UX", "ИНТЕРФЕЙС"]
        },
        "backtest": {
            "name": "BacktestRunner - Валидация стратегий",
            "file": "10_backtest.txt", 
            "keywords": ["МОДУЛЬ 7", "BacktestRunner", "ВАЛИДАЦИЯ СТРАТЕГИЙ"]
        },
        "machine_learning": {
            "name": "Система обучения и адаптации",
            "file": "11_machine_learning.txt",
            "keywords": ["МОДУЛЬ 8", "ОБУЧЕНИЯ", "АДАПТАЦИИ"]
        },
        "monitoring": {
            "name": "Система мониторинга и алертов",
            "file": "12_monitoring.txt",
            "keywords": ["МОНИТОРИНГА", "АЛЕРТОВ"]
        },
        "integrations": {
            "name": "Интеграция с внешними системами", 
            "file": "13_integrations.txt",
            "keywords": ["ИНТЕГРАЦИЯ", "ВНЕШНИМИ СИСТЕМАМИ"]
        },
        "deployment": {
            "name": "План развертывания и эксплуатации",
            "file": "14_deployment.txt",
            "keywords": ["РАЗВЕРТЫВАНИЯ", "ЭКСПЛУАТАЦИИ"]
        },
        "technical_requirements": {
            "name": "Технические требования и настройка",
            "file": "15_technical_requirements.txt", 
            "keywords": ["ТЕХНИЧЕСКИЕ ТРЕБОВАНИЯ", "НАСТРОЙКА", "СИСТЕМНЫЕ ТРЕБОВАНИЯ"]
        },
        "development_plan": {
            "name": "План дальнейшего развития",
            "file": "16_development_plan.txt",
            "keywords": ["ДАЛЬНЕЙШЕГО РАЗВИТИЯ", "ФИНАЛЬНЫЕ РЕКОМЕНДАЦИИ"]
        },
        "technical_issues": {
            "name": "Технические проблемы и решения",
            "file": "17_technical_issues.txt",
            "keywords": ["ТЕХНИЧЕСКИЕ ПРОБЛЕМЫ", "РЕШЕНИЯ", "OCR", "индексации"]
        }
    }
    
    # Проверка входного файла
    if not os.path.exists(input_file):
        print(f"❌ Файл {input_file} не найден!")
        return
    
    # Создание выходной папки
    Path(output_dir).mkdir(exist_ok=True)
    
    print(f"🔄 Читаю {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    total_lines = len(lines)
    
    print(f"📄 Всего строк: {total_lines}")
    
    # Поиск границ разделов по заголовкам
    section_boundaries = []
    
    for i, line in enumerate(lines):
        # Ищем основные заголовки разделов
        if re.match(r'^# (МОДУЛЬ|ПРАВИЛЬНОЕ|ФИЛОСОФИЯ|СИСТЕМА|ИНТЕГРАЦИЯ|ПЛАН|ТЕХНИЧЕСКИЕ|ФИНАЛЬНЫЕ)', line):
            section_boundaries.append((i, line.strip()))
    
    section_boundaries.append((total_lines, "# END"))  # Добавляем конец файла
    
    print(f"🔍 Найдено разделов: {len(section_boundaries)-1}")
    
    # Извлечение и сохранение разделов
    for i in range(len(section_boundaries)-1):
        start_line = section_boundaries[i][0]
        end_line = section_boundaries[i+1][0]
        section_title = section_boundaries[i][1]
        
        section_content = lines[start_line:end_line]
        section_text = '\n'.join(section_content)
        
        # Определение типа раздела и имени файла
        section_key = None
        output_file = None
        
        for key, meta in sections.items():
            if any(keyword in section_title for keyword in meta["keywords"]):
                section_key = key
                output_file = meta["file"]
                break
        
        # Если не нашли точное совпадение, создаем файл по номеру
        if not output_file:
            section_num = str(i+1).zfill(2)
            clean_title = re.sub(r'[^\w\s-]', '', section_title).strip()
            clean_title = re.sub(r'\s+', '_', clean_title)[:50]
            output_file = f"{section_num}_{clean_title}.txt"
        
        output_path = os.path.join(output_dir, output_file)
        
        # Создание заголовка для файла
        file_header = f"""# {section_title}
# Извлечено из baza.txt (строки {start_line+1}-{end_line})
# Дата создания: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

"""
        
        # Сохранение раздела
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(file_header + section_text)
        
        print(f"✅ Сохранен: {output_file} ({len(section_content)} строк)")
    
    # Создание индексного файла
    create_index_file(output_dir, sections)
    
    print(f"🎉 Готово! Создано файлов в папке {output_dir}/")


def create_index_file(output_dir, sections):
    """Создает индексный файл со списком всех разделов"""
    
    index_content = f"""# ИНДЕКС БАЗЫ ЗНАНИЙ FPF BOT
# Создан: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Этот каталог содержит разбитую на разделы базу знаний FPF Bot.

## СТРУКТУРА ФАЙЛОВ:

"""
    
    # Получаем список файлов в папке
    files_in_dir = sorted([f for f in os.listdir(output_dir) if f.endswith('.txt')])
    
    for filename in files_in_dir:
        if filename == '00_INDEX.txt':
            continue
            
        # Ищем описание в sections
        section_name = "Неизвестный раздел"
        for key, meta in sections.items():
            if meta["file"] == filename:
                section_name = meta["name"]
                break
        
        index_content += f"- `{filename}` - {section_name}\n"
    
    index_content += f"""
## КАК ИСПОЛЬЗОВАТЬ:

1. Используй файлы по номерам для последовательного изучения
2. Каждый файл содержит полную информацию по своей теме
3. Начни с `01_fpf_pattern.txt` для понимания основ
4. Затем изучи архитектуру в `03_architecture.txt` и `04_stream_core.txt`

## БЫСТРЫЙ ПОИСК:

- **Паттерн FPF**: `01_fpf_pattern.txt`
- **Архитектура**: `03_architecture.txt`, `04_stream_core.txt`
- **Детекторы**: `06_fpf_detector.txt`, `07_context_filters.txt`
- **UI и алерты**: `09_ui_system.txt`, `12_monitoring.txt`
- **Проблемы**: `17_technical_issues.txt`
"""
    
    index_path = os.path.join(output_dir, "00_INDEX.txt")
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(index_content)


if __name__ == "__main__":
    split_baza_file()
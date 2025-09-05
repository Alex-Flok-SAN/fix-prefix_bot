#!/usr/bin/env python3
"""
Менеджер базы знаний FPF Bot
Позволяет обновлять отдельные разделы базы знаний и автосинхронизировать с GitHub
"""

from pathlib import Path
from datetime import datetime
import subprocess

class KnowledgeManager:
    """Управление разделами базы знаний"""
    
    def __init__(self):
        self.baza_path = Path("/Users/sashaflok/fpf_bot/baza")
        self.sections = {
            "pattern": "01_fpf_pattern.txt",
            "philosophy": "02_philosophy.txt", 
            "architecture": "03_architecture.txt",
            "stream": "04_stream_core.txt",
            "levels": "05_level_engine.txt",
            "detector": "06_fpf_detector.txt",
            "filters": "07_context_filters.txt",
            "signals": "08_signal_manager.txt",
            "ui": "09_ui_system.txt",
            "backtest": "10_backtest.txt",
            "ml": "11_machine_learning.txt",
            "monitoring": "12_monitoring.txt",
            "integrations": "13_integrations.txt",
            "deployment": "14_deployment.txt",
            "requirements": "15_technical_requirements.txt",
            "roadmap": "16_development_plan.txt",
            "issues": "17_technical_issues.txt"
        }
        
    def update_section(self, section_key, content, description=None):
        """Обновляет конкретный раздел базы знаний"""
        if section_key not in self.sections:
            print(f"❌ Неизвестный раздел: {section_key}")
            print(f"📋 Доступные разделы: {', '.join(self.sections.keys())}")
            return False
            
        file_path = self.baza_path / self.sections[section_key]
        
        # Добавляем заголовок обновления
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_header = f"# Обновлено: {timestamp}\n"
        if description:
            update_header += f"# Изменения: {description}\n"
        update_header += "\n"
        
        # Читаем существующий контент
        if file_path.exists():
            existing_content = file_path.read_text()
            
            # Добавляем новый контент (либо заменяем, либо дополняем)
            if content.startswith("REPLACE:"):
                # Полная замена
                new_content = update_header + content[8:].strip()
            else:
                # Дополнение в конец
                new_content = existing_content.rstrip() + f"\n\n{update_header}{content}"
        else:
            # Новый файл
            new_content = update_header + content
            
        # Сохраняем
        file_path.write_text(new_content)
        print(f"✅ Обновлен раздел: {section_key} ({self.sections[section_key]})")
        
        return True
        
    def add_universal_fpf_info(self):
        """Добавляет информацию о универсальности FPF паттерна"""
        
        # Обновляем раздел паттерна
        universal_pattern_info = """
## УНИВЕРСАЛЬНОСТЬ FPF ПАТТЕРНА

**ВАЖНО**: FPF (Fix-Prefix-Fix) - это универсальная разворотная модель, которая работает в обе стороны:

### ЛОНГОВЫЕ FPF МОДЕЛИ

#### Последовательность формирования ЛОНГОВОГО FIX-PREFIX:

1. **FIX ОБЛАСТЬ (ПЛАТО FIX)** - Консолидация на дне
   - Цена из флэта идет вниз
   - Образует дно - ПЛАТО FIX (область консолидации на дне)
   - Это зона накопления Smart Money для будущих покупок

2. **ВЫХОД ВВЕРХ ИЗ FIX**
   - После FIX цена выходит вверх
   - Идет какое-то время вверх, образуя HI-FIX
   - HI-FIX = самый высокий HIGH после выхода из FIX области

3. **ВОЗВРАТ НИЖЕ FIX**
   - Цена идет вниз ниже области FIX
   - Как только цена прошла ниже FIX, фиксируем HI-FIX
   - HI-FIX = самый высокий хай между областью FIX и текущей ценой

4. **LOW-PATTERN (ДОННАЯ ТОЧКА)**
   - Цена идет еще ниже (высота падения варьируется)
   - Формирует Low-pattern (дно разворота)
   - После Low-pattern цена разворачивается вверх

5. **RAY (ЛУЧ ВАЛИДАЦИИ)**
   - Как только цена от Low-pattern пошла вверх, рисуем RAY вправо от HI-FIX
   - RAY = горизонтальная линия от самого высокого хая между FIX и Low-pattern

6. **ВАЛИДАЦИЯ ПАТТЕРНА**
   - Цена идет выше, проходит по высоте область FIX
   - **КАК ТОЛЬКО ЦЕНА ПРОЙДЕТ СНИЗУ-ВВЕРХ УРОВЕНЬ RAY ХОТЯ БЫ НА 1-2 ТИКА**
   - **ТОГДА ПАТТЕРН ВАЛИДИРУЕТСЯ И ОПРЕДЕЛЯЕТСЯ ОБЛАСТЬ PREFIX**

7. **PREFIX ОБЛАСТЬ (ЦЕЛЕВАЯ ЗОНА)**
   - PREFIX по высоте равен области FIX
   - PREFIX = наша целевая область для лимитников в ЛОНГ
   - Цена чаще идет выше HI-FIX перед заходом в PREFIX

### ТОРГОВАЯ ЛОГИКА ЛОНГОВЫХ МОДЕЛЕЙ:
- **Вход:** Лимитники в области PREFIX (лонг)
- **Стоп:** Ниже PREFIX области
- **Частичная фиксация:** BA75 (75% позиции при возврате)
- **Полная фиксация:** Уровень окончания движения от FIX

### ТЕКУЩИЙ ФОКУС РАЗРАБОТКИ
На данном этапе система фокусируется на **ШОРТОВЫХ моделях** для отработки алгоритмов детекции, но архитектура готова для двунаправленной торговли.
"""

        self.update_section("pattern", universal_pattern_info, "Добавлена информация о лонговых FPF моделях")
        
        # Обновляем философию
        philosophy_update = """
## УНИВЕРСАЛЬНОСТЬ ТОРГОВОГО ИНТЕЛЛЕКТА

Система FPF Bot создается как **двунаправленный торговый интеллект**:

### АДАПТИВНОСТЬ К РЫНОЧНЫМ ЦИКЛАМ
- **Bull Market**: Фокус на лонговые FPF модели, шорты только на коррекциях
- **Bear Market**: Приоритет шортовым моделям, лонги в зонах перепроданности  
- **Sideways Market**: Равное внимание обеим моделям

### ПСИХОЛОГИЯ ДВУНАПРАВЛЕННОЙ ТОРГОВЛИ

#### Smart Money в лонговых циклах:
- Накапливают активы на донышках (FIX области)
- Создают ложные пробои вниз для сбора ликвидности
- Используют retail панику для лучших входов

#### Smart Money в шортовых циклах:
- Распределяют позиции на вершинах (FIX области)
- Создают ложные пробои вверх для привлечения retail
- Используют FOMO для максимизации продаж

### ЭВОЛЮЦИЯ К ПОЛНОЙ УНИВЕРСАЛЬНОСТИ
Текущая разработка шортовых алгоритмов - это **первый этап** создания универсальной системы, которая будет:
1. Автоматически определять рыночный цикл
2. Переключаться между лонг/шорт стратегиями  
3. Адаптировать параметры под текущие условия
"""

        self.update_section("philosophy", philosophy_update, "Расширена философия для двунаправленной торговли")
        
    def create_architecture_file(self):
        """Создает отсутствующий файл архитектуры"""
        
        architecture_content = """# АРХИТЕКТУРА СИСТЕМЫ FPF BOT
# Создан: {timestamp}
# Общая архитектура торгового интеллекта

# АРХИТЕКТУРА СИСТЕМЫ FPF BOT  
# =============================================================================

## ОБЩАЯ КОНЦЕПЦИЯ АРХИТЕКТУРЫ

FPF Bot построен по **модульной event-driven архитектуре** с четким разделением ответственности:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   DATA LAYER    │    │  LOGIC LAYER    │    │    UI LAYER     │
│                 │    │                 │    │                 │
│  StreamCore     │───▶│  FPFDetector    │───▶│  MainWindow     │
│  LevelEngine    │    │  SignalManager  │    │  SignalsPanel   │
│  DataFetcher    │    │  ContextFilters │    │  FiltersPanel   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ STORAGE LAYER   │    │  SERVICE LAYER  │    │ INTEGRATION     │
│                 │    │                 │    │                 │
│  Database       │    │  EventBus       │    │  TelegramBot    │
│  FileStorage    │    │  TaskScheduler  │    │  TradingView    │
│  CloudSync      │    │  ErrorHandler   │    │  BinanceAPI     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## ПРИНЦИПЫ АРХИТЕКТУРЫ

### 1. EVENT-DRIVEN DESIGN
Вся система работает через события:
- `CandleClosedEvent` → запускает анализ уровней и паттернов
- `PatternDetectedEvent` → активирует фильтры и валидацию  
- `SignalGeneratedEvent` → отправляет уведомления и логирует

### 2. LOOSE COUPLING
Модули общаются только через EventBus:
```python
# Модуль A не знает о модуле B напрямую
event_bus.emit(PatternDetectedEvent(pattern_data))

# Модуль B подписан на события
@event_bus.subscribe(PatternDetectedEvent)
def handle_pattern(event):
    # Обработка события
```

### 3. SINGLE RESPONSIBILITY
Каждый модуль имеет одну четкую функцию:
- **StreamCore**: Только получение и агрегация данных
- **FPFDetector**: Только детекция паттернов
- **ContextFilters**: Только фильтрация сигналов
- **SignalManager**: Только управление жизненным циклом сигналов

### 4. FAIL-SAFE OPERATION
Система продолжает работу при сбое модулей:
```python
try:
    pattern = fpf_detector.detect_pattern(candles)
except Exception as e:
    logger.error(f"FPF detection failed: {e}")
    # Система продолжает работу без этого паттерна
    pattern = None
```

## ПОДРОБНАЯ АРХИТЕКТУРА МОДУЛЕЙ

### DATA LAYER - Слой данных

#### StreamCore
- **Назначение**: Единый источник рыночных данных
- **Входы**: Binance WebSocket/REST API
- **Выходы**: CandleClosedEvent для всех ТФ
- **Ключевые особенности**:
  - Агрегация M1 → M5 → M15 → H1 → H4
  - Валидация данных и детекция пропусков
  - Автоматическое переключение WS ↔ REST при сбоях

#### LevelEngine  
- **Назначение**: Расчет значимых рыночных уровней
- **Входы**: CandleClosedEvent
- **Выходы**: LevelUpdatedEvent
- **Расчетные уровни**:
  - HOD/LOD (High/Low of Day)
  - POC (Point of Control) 
  - VWAP (Volume Weighted Average Price)
  - Swing точки

### LOGIC LAYER - Слой бизнес-логики

#### FPFDetector
- **Назначение**: Детекция паттернов Fix-Prefix-Fix
- **State Machine**: 8 состояний от IDLE до PATTERN_COMPLETE
- **Алгоритмы**:
  - Поиск FIX областей (консолидация)
  - Построение RAY линий (валидация)
  - Определение PREFIX зон (входы)
  - Расчет confidence score

#### ContextFilters
- **Назначение**: Интеллектуальная фильтрация сигналов
- **5 фильтров с весами**:
  - Volume (30%) - самый важный
  - ATR (25%) - волатильность
  - Level (20%) - близость к уровням
  - Session (15%) - торговые сессии
  - Multi-TF (10%) - подтверждение старшими ТФ

#### SignalManager
- **Назначение**: Управление жизненным циклом сигналов
- **Функции**:
  - Агрегация сигналов с разных ТФ
  - Устранение конфликтов
  - Отслеживание результатов
  - Обучение на исторических данных

### SERVICE LAYER - Сервисный слой

#### EventBus
- **Назначение**: Центральная шина событий
- **Особенности**:
  - Асинхронная обработка
  - Приоритеты событий
  - Batch processing для производительности
  - Error handling и retry логика

#### TaskScheduler
- **Назначение**: Планирование фоновых задач
- **Задачи**:
  - Периодическая очистка данных
  - Обновление ML моделей
  - Синхронизация с внешними API
  - Генерация отчетов

## ПОТОКИ ДАННЫХ

### Основной поток торговых сигналов:
```
Binance WS → StreamCore → CandleClosedEvent →
LevelEngine → LevelUpdatedEvent →
FPFDetector → PatternDetectedEvent →  
ContextFilters → SignalValidatedEvent →
SignalManager → SignalGeneratedEvent →
UI + Telegram + Logging
```

### Поток обратной связи (обучение):
```
SignalResult → ML Pipeline → Model Update →
ContextFilters Parameter Adjustment →
Improved Signal Quality
```

## МАСШТАБИРУЕМОСТЬ

### Горизонтальное масштабирование:
- Каждый символ может обрабатываться отдельным процессом
- EventBus поддерживает распределенную архитектуру
- База данных может быть шардирована по символам

### Вертикальное масштабирование:
- Модули могут использовать многопоточность
- Batch processing для высокой нагрузки
- Кэширование вычислений уровней и паттернов

## БЕЗОПАСНОСТЬ И НАДЕЖНОСТЬ

### Error Handling:
- Каждый модуль изолирован try/catch блоками
- Graceful degradation при сбоях
- Автоматические retry для внешних API

### Data Integrity:
- Валидация входящих данных
- Детекция и коррекция пропусков
- Backup и восстановление состояния

### Security:
- Шифрование API ключей
- Ограничение rate limits
- Логирование всех операций

## МОНИТОРИНГ И МЕТРИКИ

### Performance Metrics:
- Задержка обработки событий
- Использование CPU/RAM
- Количество обработанных тиков

### Business Metrics:
- Win rate сигналов
- Profit factor
- Maximum drawdown
- Sharpe ratio

### System Health:
- Статус подключений к API
- Очереди событий
- Ошибки и исключения

---

Эта архитектура обеспечивает:
✅ **Надежность** - система продолжает работу при сбоях модулей
✅ **Масштабируемость** - легко добавлять новые модули и функции  
✅ **Производительность** - event-driven и асинхронная обработка
✅ **Гибкость** - модули могут быть заменены без влияния на систему
✅ **Тестируемость** - каждый модуль может быть протестирован изолированно""".format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        file_path = self.baza_path / "03_architecture.txt"
        file_path.write_text(architecture_content)
        print("✅ Создан файл архитектуры: 03_architecture.txt")
        
        # Обновляем индекс
        self._update_index()
        
    def _update_index(self):
        """Обновляет файл индекса"""
        index_path = self.baza_path / "00_INDEX.txt"
        if index_path.exists():
            content = index_path.read_text()
            
            # Добавляем архитектуру если её нет
            if "03_architecture.txt" not in content:
                updated_content = content.replace(
                    "- `02_philosophy.txt` - Философия и концепция проекта",
                    """- `02_philosophy.txt` - Философия и концепция проекта
- `03_architecture.txt` - Общая архитектура системы"""
                )
                
                # Обновляем дату создания
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                updated_content = updated_content.replace(
                    "# Создан: 2025-08-29 19:03:09",
                    f"# Создан: 2025-08-29 19:03:09\n# Обновлен: {timestamp}"
                )
                
                index_path.write_text(updated_content)
                print("✅ Обновлен индекс базы знаний")
                
    def sync_to_github(self, message=None):
        """Синхронизирует изменения с GitHub"""
        try:
            if message:
                subprocess.run([
                    "python3", "/Users/sashaflok/fpf_bot/sync_knowledge_base.py", message
                ], check=True)
            else:
                subprocess.run([
                    "python3", "/Users/sashaflok/fpf_bot/sync_knowledge_base.py"
                ], check=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка синхронизации с GitHub: {e}")


def main():
    """Основная функция для CLI"""
    import sys
    
    manager = KnowledgeManager()
    
    if len(sys.argv) < 2:
        print("📚 Менеджер базы знаний FPF Bot")
        print("═" * 40)
        print("Команды:")
        print("  universal    - Добавить информацию о универсальности FPF")
        print("  architecture - Создать файл архитектуры")
        print("  sync [msg]   - Синхронизировать с GitHub")
        print("  update <section> <content> - Обновить раздел")
        print(f"\nРазделы: {', '.join(manager.sections.keys())}")
        return
        
    command = sys.argv[1]
    
    if command == "universal":
        manager.add_universal_fpf_info()
        manager.sync_to_github("📈 Добавлена информация о универсальности FPF паттерна")
        
    elif command == "architecture":
        manager.create_architecture_file()
        manager.sync_to_github("🏗️ Создан файл архитектуры системы")
        
    elif command == "sync":
        message = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
        manager.sync_to_github(message)
        
    elif command == "update" and len(sys.argv) >= 4:
        section = sys.argv[2]
        content = " ".join(sys.argv[3:])
        if manager.update_section(section, content):
            manager.sync_to_github(f"📝 Обновлен раздел {section}")
    else:
        print("❌ Неверная команда или недостаточно аргументов")


if __name__ == "__main__":
    main()
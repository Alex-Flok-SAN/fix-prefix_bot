# FPF Bot Knowledge Base

Структурированная база знаний торговой системы **FPF Bot** для детекции паттернов Fix-Prefix-Fix на криптовалютных рынках.

## 🎯 О проекте

**FPF Bot** - это интеллектуальная торговая система, которая:
- Детектирует разворотные паттерны Fix-Prefix-Fix
- Анализирует поведение Smart Money vs Retail трейдеров
- Использует машинное обучение для адаптации к рынку
- Интегрируется с TradingView через OCR

## 📚 Структура базы знаний

База знаний разделена на тематические разделы:

### Основы
- [`01_fpf_pattern.txt`](baza/01_fpf_pattern.txt) - Определение FPF паттерна
- [`02_philosophy.txt`](baza/02_philosophy.txt) - Философия и концепция проекта

### Архитектура системы  
- [`04_stream_core.txt`](baza/04_stream_core.txt) - StreamCore - фундамент системы
- [`05_level_engine.txt`](baza/05_level_engine.txt) - LevelEngine - анализ рыночных уровней
- [`06_fpf_detector.txt`](baza/06_fpf_detector.txt) - FPFDetector - детекция паттернов
- [`07_context_filters.txt`](baza/07_context_filters.txt) - Фильтрация сигналов
- [`08_signal_manager.txt`](baza/08_signal_manager.txt) - Управление сигналами

### UI и интеграции
- [`09_ui_system.txt`](baza/09_ui_system.txt) - Система пользовательского интерфейса
- [`12_monitoring.txt`](baza/12_monitoring.txt) - Мониторинг и алерты
- [`13_integrations.txt`](baza/13_integrations.txt) - Внешние интеграции

### Тестирование и ML
- [`10_backtest.txt`](baza/10_backtest.txt) - Система бэктестинга
- [`11_machine_learning.txt`](baza/11_machine_learning.txt) - Машинное обучение

### Развертывание
- [`14_deployment.txt`](baza/14_deployment.txt) - План развертывания
- [`15_technical_requirements.txt`](baza/15_technical_requirements.txt) - Технические требования
- [`16_development_plan.txt`](baza/16_development_plan.txt) - План развития

### Проблемы и решения
- [`17_technical_issues.txt`](baza/17_technical_issues.txt) - Технические проблемы

## 🚀 Быстрый старт

1. Ознакомьтесь с [`00_INDEX.txt`](baza/00_INDEX.txt) для навигации
2. Начните с [`01_fpf_pattern.txt`](baza/01_fpf_pattern.txt) для понимания основ
3. Изучите архитектуру в [`04_stream_core.txt`](baza/04_stream_core.txt)

## 📈 Торговая стратегия

**Fix-Prefix-Fix** - универсальная разворотная модель, работающая в обе стороны:

1. **FIX** - область консолидации (накопление Smart Money)
2. **PREFIX** - тестирование силы и ликвидности  
3. **IMPULSE** - направленное движение с высвобождением энергии

## 🔧 Технический стек

- **Backend**: Python, pandas, asyncio
- **Data**: Binance WebSocket/REST API
- **ML**: XGBoost, LightGBM, Neural Networks
- **UI**: PyQt5, Tkinter
- **Integrations**: TradingView OCR, Telegram

## 📞 Контакты

Проект разрабатывается для создания торгового интеллекта нового поколения.

---

*Последнее обновление: $(date '+%Y-%m-%d')*

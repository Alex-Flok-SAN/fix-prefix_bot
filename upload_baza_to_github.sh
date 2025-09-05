#!/bin/bash
# Скрипт для загрузки базы знаний на GitHub
# Использование: ./upload_baza_to_github.sh [repository_name]

set -e  # Останавливаемся при первой ошибке

REPO_NAME=${1:-"fpf-bot-knowledge-base"}
GITHUB_USERNAME="Alex-Flok-SAN"  # Замени на свой username если нужно

echo "🚀 Загрузка базы знаний FPF Bot на GitHub..."
echo "📂 Репозиторий: $REPO_NAME"
echo "👤 Пользователь: $GITHUB_USERNAME"

# Переходим в папку с базой знаний
cd /Users/sashaflok/fpf_bot

# Создаем временную папку для репозитория
TEMP_REPO="/tmp/$REPO_NAME"
rm -rf "$TEMP_REPO"
mkdir -p "$TEMP_REPO"

echo "📋 Копируем файлы базы знаний..."

# Копируем всю папку baza
cp -r baza "$TEMP_REPO/"

# Копируем связанные файлы
cp PROJECT_STRUCTURE.md "$TEMP_REPO/" 2>/dev/null || echo "⚠️ PROJECT_STRUCTURE.md не найден"

# Создаем README для репозитория
cat > "$TEMP_REPO/README.md" << 'EOF'
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
EOF

# Создаем .gitignore
cat > "$TEMP_REPO/.gitignore" << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/
.env

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Data files
*.csv
*.parquet
*.db
*.sqlite

# Temporary files
temp/
tmp/
*.tmp
EOF

echo "📂 Инициализируем Git репозиторий..."
cd "$TEMP_REPO"

# Инициализация Git
git init
git add .
git commit -m "🎯 Initial commit: FPF Bot Knowledge Base

📚 Structured knowledge base for FPF trading system
🔍 Includes pattern detection algorithms and system architecture
📊 Ready for development and deployment

🚀 Generated with Claude Code
https://claude.ai/code

Co-Authored-By: Claude <noreply@anthropic.com>"

echo "🌐 Создаем удаленный репозиторий на GitHub..."

# Создаем репозиторий через GitHub API (требует GitHub CLI или токен)
if command -v gh &> /dev/null; then
    echo "✅ Используем GitHub CLI..."
    gh repo create "$REPO_NAME" --public --description "🎯 FPF Bot Knowledge Base - Structured documentation for Fix-Prefix-Fix trading system" --clone=false
    git remote add origin "https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"
else
    echo "⚠️ GitHub CLI не найден. Создайте репозиторий вручную:"
    echo "   1. Откройте https://github.com/new"
    echo "   2. Название: $REPO_NAME"  
    echo "   3. Описание: FPF Bot Knowledge Base - Structured documentation for Fix-Prefix-Fix trading system"
    echo "   4. Публичный репозиторий"
    echo "   5. Не добавляйте README, .gitignore, license"
    echo ""
    echo "📋 Затем выполните:"
    echo "   git remote add origin https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"
    read -p "Нажмите Enter когда создадите репозиторий..."
    git remote add origin "https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"
fi

echo "📤 Загружаем на GitHub..."
git branch -M main
git push -u origin main

echo "🎉 Готово! База знаний загружена:"
echo "🔗 https://github.com/$GITHUB_USERNAME/$REPO_NAME"
echo ""
echo "📂 Временные файлы: $TEMP_REPO"
echo "🗑️ Удалить временную папку? (y/n)"
read -r cleanup
if [[ $cleanup =~ ^[Yy]$ ]]; then
    rm -rf "$TEMP_REPO"
    echo "✅ Временные файлы удалены"
fi

echo ""
echo "🚀 Успешно! Теперь база знаний доступна на GitHub."
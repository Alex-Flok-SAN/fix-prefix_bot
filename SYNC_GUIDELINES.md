# 🎯 GitHub Sync Guidelines - Избирательная Синхронизация

## 📋 **Принципы синхронизации**

Этот проект настроен на **избирательную синхронизацию** - в GitHub попадают только **утвержденные и готовые изменения**.

## 🔄 **Типы синхронизации**

### 💾 **Локальная разработка** (НЕ синхронизируется)
```bash
# Обычные коммиты для текущей работы
git add .
git commit -m "🔧 Work in progress - refactoring FPF detector"
# НЕ отправляется в GitHub автоматически
```

### 🎯 **Утвержденная синхронизация** (синхронизируется в GitHub)
```bash
# Использовать скрипт approved_sync.sh
./scripts/approved_sync.sh stable "Fix FPF pattern detection algorithm"
./scripts/approved_sync.sh release "Major update - complete FPF system"
./scripts/approved_sync.sh hotfix "Critical bug fix - OCR interpretation"
./scripts/approved_sync.sh production "Production ready - v2.0"
```

## 📝 **Как работать**

### ⚙️ **В VSCode:**
1. **Локальная работа:** `Ctrl+Shift+P` → "💾 Local Commit Only"
2. **Утверженные изменения:** `Ctrl+Shift+P` → "🎯 Approved Sync to GitHub"

### 🎚️ **Типы релизов:**

- **`stable`** - Стабильные изменения, готовые к использованию
- **`release`** - Крупные обновления с новым функционалом  
- **`hotfix`** - Критические исправления багов
- **`production`** - Полностью протестированные production-ready версии

## 🚫 **Что НЕ синхронизируется автоматически:**

- Файлы с суффиксами `*_temp.py`, `*_debug.py`, `*_wip.py`
- Папки `/wip/`, `/temp/`, `/experiments/`
- Логи разработки `*.dev.json`, `/logs_dev/`
- Локальные конфигурации `*_local.*`
- Временные файлы `*.tmp`, `*.backup`

## ✅ **Что синхронизируется:**

- Готовый код с тестами
- Обновленная документация
- Финальные конфигурации
- База знаний после проверки
- Производственные скрипты

## 🏷️ **Система тегирования:**

Каждая утвержденная синхронизация создает тег:
- `stable/20250905_143022` - стабильное обновление
- `release/20250905_150000` - релиз версии
- `hotfix/20250905_160000` - критическое исправление
- `production/20250905_170000` - production деплой

## 🎯 **Workflow:**

### 🔧 Ежедневная разработка:
```bash
# 1. Работаем локально
git add .
git commit -m "🔧 Testing new FPF parameters"

# 2. Еще больше изменений
git commit -m "🔧 Debugging OCR accuracy"

# 3. НЕ отправляем в GitHub - работаем локально
```

### 🚀 Готовы к релизу:
```bash
# Когда все протестировано и готово:
./scripts/approved_sync.sh stable "Improved FPF detection accuracy by 15%"

# Автоматически:
# - Создается тег stable/TIMESTAMP
# - Отправляется в GitHub
# - Создается GitHub Release
```

## ⚡ **Быстрые команды:**

```bash
# Локальный коммит (только в локальный Git)
git add . && git commit -m "🔧 WIP: refactoring"

# Утвержденная синхронизация (в GitHub)
./scripts/approved_sync.sh stable "Ready for production"
```

## 🔒 **Защита от случайной синхронизации:**

- ❌ Auto-fetch отключен
- ❌ Smart commit отключен  
- ❌ Auto-sync отключен
- ✅ Confirmation required для push
- ✅ Только утвержденные релизы в GitHub

---

## 💡 **Принцип:**

**"GitHub = Production Repository"**  
**"Local Git = Development Playground"**

Разрабатываем локально, синхронизируем только готовое! 🎯
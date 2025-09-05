# 💾 Session Cache - FPF Bot Project

## 📅 **Последнее обновление:** 2025-09-05 06:53:07

---

## 🎯 **ТЕКУЩЕЕ СОСТОЯНИЕ ПРОЕКТА**

### ✅ **Выполненные задачи:**
1. **Создана избирательная синхронизация с GitHub** - только утвержденные изменения
2. **Настроена интеграция с веб-версией Claude** - может читать проект через GitHub
3. **Система автоматического контекста** - промпты обновляются при изменениях
4. **GitHub Sync Daemon** - отслеживает изменения и обновляет контекст
5. **Session Cache** - кэширование состояния перед перезагрузкой

### 🔧 **Git Status:**
```
Ветка: main

Статус файлов:
M claude_prompts/all_prompts.json
 M claude_prompts/latest_changes.txt
 M claude_prompts/main_context.txt
 M logs/github_sync_daemon.out
 M logs/last_commit.txt
 M scripts/save_context.sh
 M scripts/save_session_context.py
?? SESSION_CACHE.md

Незакоммиченные файлы:
claude_prompts/all_prompts.json
claude_prompts/latest_changes.txt
claude_prompts/main_context.txt
logs/github_sync_daemon.out
logs/last_commit.txt
scripts/save_context.sh
scripts/save_session_context.py

Последние коммиты:
131c8e8 🎯 [stable] Complete Session Context System - save/restore functionality ready
4bc2a97 🎯 [stable] Complete Claude Web Integration - GitHub sync system ready
a9f1424 🎯 [stable] Configure selective GitHub sync - only approved changes
34fa2e3 🚀 Complete FPF Bot Project Upload
ba9a073 🔧 Add VSCode configuration for seamless GitHub sync
```

### 🤖 **Запущенные процессы:**
```json
{
  "github_sync_daemon": {
    "pid": "42770",
    "running": true
  }
}
```

---

## 💻 **КОМАНДЫ ДЛЯ ТЕРМИНАЛА**

### 🔧 **Разработка:**
```bash
git add . && git commit -m '🔧 Work in progress'
./scripts/approved_sync.sh stable 'Feature ready'
python3 scripts/generate_claude_context.py
```

### 🤖 **Демон синхронизации:**
```bash
./scripts/github_sync_control.sh start
./scripts/github_sync_control.sh status
./scripts/github_sync_control.sh sync
./scripts/github_sync_control.sh stop
```

### 📊 **Мониторинг:**
```bash
git status
git log --oneline -5
ls claude_prompts/
tail -f logs/github_sync.log
```

### 🌐 **Веб-интеграция:**
```bash
cat claude_prompts/main_context.txt
python3 scripts/github_sync_daemon.py --once
ls -la claude_prompts/
```

---

## 📁 **СТРУКТУРА ПРОЕКТА**

### 📂 **Основные файлы (218 файлов):**
```
./test_fix_persistence.py
./visualization/pattern_drawer.py
./visualization/chart_renderer.py
./visualization/__init__.py
./ui/filters_panel.py
./ui/signals_panel.py
./ui/__init__.py
./ui/tv_ingest_window.py
./ui/pattern_analyzer.py
./SESSION_CACHE.md
./.github_sync_daemon.pid
./tools/snapp.py
./tools/.DS_Store
./tools/label_maker_gui.py
./tools/tv_ingest_refactored.py
./tools/fpf_pattern_builder.py
./tools/tv_fetch.py
./tools/tv_ingest_hybrid.py
./final_pattern_test.py
./UPDATE_KNOWLEDGE_BASE_INSTRUCTIONS.md
./CLAUDE_WEB_INTEGRATION.md
./analyze_screenshot.py
./PATTERN_ANALYSIS_COMPLETE.md
./PROJECT_STRUCTURE.md
./core/persist.py
./core/signal_manager.py
./core/series.py
./core/ai_search_pattern/fpf_detector_new.py
./core/ai_search_pattern/__init__.py
./core/ai_search_pattern/inference
... и еще 188 файлов
```

---

## 🔗 **КЛЮЧЕВЫЕ ССЫЛКИ**

### 🌐 **GitHub Repository:**
https://github.com/Alex-Flok-SAN/fix-prefix_bot

### 📱 **Для веб-версии Claude:**
```
Загрузи кэш FPF Bot проекта:
https://raw.githubusercontent.com/Alex-Flok-SAN/fix-prefix_bot/main/SESSION_CACHE.md

И основную базу знаний:
https://raw.githubusercontent.com/Alex-Flok-SAN/fix-prefix_bot/main/ULTIMATE_KNOWLEDGE_BASE_GUIDE_FOR_AI_TRAINING.md

Теперь продолжай с того места, где остановились!
```

---

## ⚡ **БЫСТРЫЙ СТАРТ ПОСЛЕ ПЕРЕЗАГРУЗКИ**

### 1️⃣ **Проверка статуса:**
```bash
git status
./scripts/github_sync_control.sh status
ls claude_prompts/
```

### 2️⃣ **Если нужна синхронизация:**
```bash
python3 scripts/generate_claude_context.py
./scripts/approved_sync.sh stable "Session restored"
```

### 3️⃣ **Запуск демона (если остановлен):**
```bash
./scripts/github_sync_control.sh start
```

---

## 🎯 **FPF BOT ПРОЕКТ - КРАТКАЯ СПРАВКА**

### 🔍 **Что это:**
- **Торговый бот** для паттерна **FIX-PREFIX-FIX**
- **AI-детекция** паттернов через OCR скриншотов
- **Веб-интеграция** с Claude для удаленной разработки
- **Избирательная синхронизация** - только готовый код в GitHub

### ⚙️ **Основные компоненты:**
- `core/ai_search_pattern/` - AI движок поиска
- `ai/ocr_engine.py` - OCR распознавание текста
- `visualization/` - Визуализация паттернов
- `baza/` - База знаний (22 файла)
- `scripts/` - Скрипты управления

### 🎯 **Паттерн FIX-PREFIX-FIX:**
**Последовательность:** FIX → LOY-FIX → HI-PATTERN → RAY → PREFIX
**Применение:** Reversal trading pattern
**Точность:** ~75% детекции

---

## 📞 **ДЛЯ ПРОДОЛЖЕНИЯ РАБОТЫ:**

### 🔄 **В новой сессии Claude Code:**
1. Загружаем этот файл как контекст
2. Проверяем Git статус  
3. Продолжаем с того места, где остановились

### 📱 **В веб-версии Claude:**
1. Используем готовый промпт выше
2. Claude загружает всю базу знаний
3. Может помочь с анализом и разработкой

---

*📝 Автоматически обновляется командой: python3 scripts/save_session_context.py*  
*🕒 Последнее обновление: 2025-09-05 06:53:07*  
*🔗 GitHub: https://github.com/Alex-Flok-SAN/fix-prefix_bot*
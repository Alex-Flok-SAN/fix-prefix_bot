#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🌐 Claude Web Context Generator
Автоматически генерирует контекст для веб-версии Claude из GitHub репозитория
"""

import json
import datetime
from pathlib import Path

# GitHub repository configuration
GITHUB_REPO = "Alex-Flok-SAN/fix-prefix_bot"
GITHUB_RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main"

# Key files for Claude context
KEY_FILES = {
    "📊 База знаний": "ULTIMATE_KNOWLEDGE_BASE_GUIDE_FOR_AI_TRAINING.md",
    "🎯 FPF Паттерн": "baza/01_fpf_pattern.txt", 
    "💡 Философия": "baza/02_philosophy.txt",
    "🏗️ Архитектура": "baza/02_architecture_refactoring.txt",
    "⚡ Stream Core": "baza/04_stream_core.txt",
    "🔍 FPF Детектор": "baza/06_fpf_detector.txt",
    "🧠 AI Поиск": "core/ai_search_pattern/inference.py",
    "👁️ OCR Движок": "ai/ocr_engine.py",
    "📈 Визуализация": "visualization/pattern_drawer.py",
    "🖥️ UI Система": "ui/pattern_analyzer.py"
}

def generate_context_prompt():
    """Генерирует готовый промпт для веб-версии Claude"""
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    prompt = f"""# 🎯 FPF Bot Expert Context Loader
Время обновления: {timestamp}

Привет! Стань экспертом по моему проекту FPF Bot для торгового паттерна FIX-PREFIX-FIX.

## 📚 Загрузи базу знаний:

### 🎯 **Главная база знаний (ОБЯЗАТЕЛЬНО):**
{GITHUB_RAW_BASE}/{KEY_FILES['📊 База знаний']}

### 📋 **Ключевые компоненты системы:**
"""
    
    for name, file_path in KEY_FILES.items():
        if name != "📊 База знаний":  # Уже добавлен выше
            prompt += f"- **{name}:** {GITHUB_RAW_BASE}/{file_path}\n"
    
    prompt += f"""
## 🚀 **После загрузки ты будешь знать:**

✅ Полную архитектуру FPF Bot  
✅ Алгоритм паттерна FIX-PREFIX-FIX  
✅ Систему OCR и детекции сигналов  
✅ UI компоненты и визуализацию  
✅ AI-движок поиска паттернов  
✅ Stream-ядро обработки данных  

## 💬 **Готов к работе!**
После изучения всех файлов ответь: "🎯 FPF Bot Expert готов! База знаний загружена. Чем помочь?"

---
*Автогенерировано: {timestamp}*
*Репозиторий: https://github.com/{GITHUB_REPO}*"""
    
    return prompt

def generate_quick_prompts():
    """Генерирует быстрые промпты для разных задач"""
    
    prompts = {
        "🔍 Анализ паттерна": f"""
Изучи FPF паттерн и помоги с анализом:
{GITHUB_RAW_BASE}/{KEY_FILES['🎯 FPF Паттерн']}

Теперь помоги с анализом текущей ситуации на рынке.""",

        "🐛 Отладка кода": f"""
Проанализируй код FPF системы:
- AI детектор: {GITHUB_RAW_BASE}/{KEY_FILES['🧠 AI Поиск']}  
- OCR движок: {GITHUB_RAW_BASE}/{KEY_FILES['👁️ OCR Движок']}

Помоги найти и исправить ошибку.""",

        "🏗️ Разработка": f"""
Изучи архитектуру FPF Bot:
{GITHUB_RAW_BASE}/{KEY_FILES['📊 База знаний']}

Предложи улучшения и новые фичи.""",

        "📈 Оптимизация": f"""
Изучи систему торговых сигналов:
- FPF Детектор: {GITHUB_RAW_BASE}/{KEY_FILES['🔍 FPF Детектор']}
- Stream Core: {GITHUB_RAW_BASE}/{KEY_FILES['⚡ Stream Core']}

Помоги оптимизировать алгоритм."""
    }
    
    return prompts

def save_context_files():
    """Сохраняет сгенерированные промпты в файлы"""
    
    # Создаем директорию для промптов
    prompts_dir = Path("claude_prompts")
    prompts_dir.mkdir(exist_ok=True)
    
    # Основной контекст
    main_prompt = generate_context_prompt()
    with open(prompts_dir / "main_context.txt", "w", encoding="utf-8") as f:
        f.write(main_prompt)
    
    # Быстрые промпты
    quick_prompts = generate_quick_prompts()
    for name, prompt in quick_prompts.items():
        filename = name.replace("🔍 ", "").replace("🐛 ", "").replace("🏗️ ", "").replace("📈 ", "")
        filename = filename.replace(" ", "_").lower() + ".txt"
        
        with open(prompts_dir / filename, "w", encoding="utf-8") as f:
            f.write(prompt)
    
    # JSON со всеми промптами для программного использования
    all_prompts = {
        "main_context": main_prompt,
        "quick_prompts": quick_prompts,
        "github_repo": GITHUB_REPO,
        "generated_at": datetime.datetime.now().isoformat()
    }
    
    with open(prompts_dir / "all_prompts.json", "w", encoding="utf-8") as f:
        json.dump(all_prompts, f, ensure_ascii=False, indent=2)
    
    print("✅ Контексты сгенерированы в папке claude_prompts/")
    print(f"📁 Файлы: main_context.txt, {len(quick_prompts)} быстрых промптов, all_prompts.json")

def print_mobile_instructions():
    """Выводит инструкции для мобильного использования"""
    
    print("""
🌐 === ИНСТРУКЦИЯ ДЛЯ ТЕЛЕФОНА ===

1️⃣ Откройте https://claude.ai на телефоне
2️⃣ Скопируйте ВЕСЬ текст из claude_prompts/main_context.txt  
3️⃣ Вставьте в чат с Claude
4️⃣ Claude загрузит всю базу знаний!

📱 БЫСТРЫЕ ПРОМПТЫ:
- Анализ: claude_prompts/анализ_паттерна.txt
- Отладка: claude_prompts/отладка_кода.txt  
- Разработка: claude_prompts/разработка.txt
- Оптимизация: claude_prompts/оптимизация.txt

✨ Готово! Claude будет экспертом по вашему FPF Bot!
""")

if __name__ == "__main__":
    print("🎯 Генерация контекста для веб-версии Claude...")
    save_context_files()
    print_mobile_instructions()
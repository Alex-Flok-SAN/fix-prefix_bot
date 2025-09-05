#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
💾 Session Context Saver
Автоматически сохраняет весь контекст сессии Claude Code перед перезагрузкой
"""

import os
import json
import subprocess
from datetime import datetime
from pathlib import Path

class SessionContextSaver:
    def __init__(self):
        self.backup_file = Path("SESSION_CONTEXT_BACKUP.md")
        self.context_dir = Path("session_context")
        self.context_dir.mkdir(exist_ok=True)
        
    def get_git_status(self):
        """Получает текущий статус Git"""
        try:
            # Git status
            status_result = subprocess.run(
                ["git", "status", "--porcelain"], 
                capture_output=True, text=True
            )
            
            # Git log - последние 5 коммитов
            log_result = subprocess.run(
                ["git", "log", "--oneline", "-5"], 
                capture_output=True, text=True
            )
            
            # Current branch
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True
            )
            
            # Uncommitted changes
            diff_result = subprocess.run(
                ["git", "diff", "--name-only"],
                capture_output=True, text=True
            )
            
            return {
                "status": status_result.stdout.strip(),
                "recent_commits": log_result.stdout.strip(),
                "current_branch": branch_result.stdout.strip(),
                "uncommitted_files": diff_result.stdout.strip()
            }
            
        except Exception as e:
            return {"error": f"Ошибка получения Git статуса: {e}"}
    
    def get_project_structure(self):
        """Получает структуру проекта"""
        try:
            # Получаем дерево файлов (исключая .git, __pycache__, logs)
            tree_result = subprocess.run([
                "find", ".", 
                "-type", "f",
                "-not", "-path", "./.git/*",
                "-not", "-path", "./__pycache__/*", 
                "-not", "-path", "./logs/*",
                "-not", "-path", "./*.pyc",
                "-not", "-name", "*.log"
            ], capture_output=True, text=True)
            
            return tree_result.stdout.strip().split('\n')
            
        except Exception as e:
            return [f"Ошибка получения структуры: {e}"]
    
    def get_running_processes(self):
        """Проверяет запущенные процессы демонов"""
        processes = {}
        
        # GitHub Sync Daemon
        try:
            pid_file = Path(".github_sync_daemon.pid")
            if pid_file.exists():
                pid = pid_file.read_text().strip()
                check_result = subprocess.run(
                    ["ps", "-p", pid], 
                    capture_output=True, text=True
                )
                processes["github_sync_daemon"] = {
                    "pid": pid,
                    "running": check_result.returncode == 0
                }
        except Exception:
            processes["github_sync_daemon"] = {"status": "unknown"}
        
        return processes
    
    def get_key_files_content(self):
        """Получает содержимое ключевых файлов"""
        key_files = [
            "SYNC_GUIDELINES.md",
            "CLAUDE_WEB_INTEGRATION.md", 
            ".vscode/settings.json",
            "claude_prompts/main_context.txt",
            "requirements.txt"
        ]
        
        files_content = {}
        
        for file_path in key_files:
            try:
                path = Path(file_path)
                if path.exists():
                    # Для больших файлов берем только первые 50 строк
                    with open(path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        if len(lines) > 50:
                            content = ''.join(lines[:50]) + f"\n... (еще {len(lines)-50} строк)"
                        else:
                            content = ''.join(lines)
                    
                    files_content[file_path] = {
                        "size": len(content),
                        "lines": len(lines),
                        "content_preview": content
                    }
                else:
                    files_content[file_path] = {"status": "not_found"}
                    
            except Exception as e:
                files_content[file_path] = {"error": str(e)}
        
        return files_content
    
    def generate_terminal_command_summary(self):
        """Генерирует сводку команд для терминала"""
        
        commands = {
            "🔧 Разработка": [
                "git add . && git commit -m '🔧 Work in progress'",
                "./scripts/approved_sync.sh stable 'Feature ready'",
                "python3 scripts/generate_claude_context.py"
            ],
            "🤖 Демон синхронизации": [
                "./scripts/github_sync_control.sh start",
                "./scripts/github_sync_control.sh status", 
                "./scripts/github_sync_control.sh sync",
                "./scripts/github_sync_control.sh stop"
            ],
            "📊 Мониторинг": [
                "git status",
                "git log --oneline -5",
                "ls claude_prompts/",
                "tail -f logs/github_sync.log"
            ],
            "🌐 Веб-интеграция": [
                "cat claude_prompts/main_context.txt",
                "python3 scripts/github_sync_daemon.py --once",
                "ls -la claude_prompts/"
            ]
        }
        
        return commands
    
    def update_backup_file(self):
        """Обновляет файл резервной копии контекста"""
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Получаем всю необходимую информацию
        git_info = self.get_git_status()
        project_structure = self.get_project_structure()
        running_processes = self.get_running_processes()
        key_files = self.get_key_files_content()
        terminal_commands = self.generate_terminal_command_summary()
        
        # Формируем обновленный контент
        updated_content = f"""# 🔄 Session Context Backup - FPF Bot Project

## 📅 **Последнее обновление:** {timestamp}

---

## 🎯 **ТЕКУЩЕЕ СОСТОЯНИЕ ПРОЕКТА**

### ✅ **Выполненные задачи:**
1. **Создана избирательная синхронизация с GitHub** - только утвержденные изменения
2. **Настроена интеграция с веб-версией Claude** - может читать проект через GitHub
3. **Система автоматического контекста** - промпты обновляются при изменениях
4. **GitHub Sync Daemon** - отслеживает изменения и обновляет контекст
5. **Session Context Backup** - сохранение состояния перед перезагрузкой

### 🔧 **Git Status:**
```
Ветка: {git_info.get('current_branch', 'unknown')}

Статус файлов:
{git_info.get('status', 'Нет изменений')}

Незакоммиченные файлы:
{git_info.get('uncommitted_files', 'Нет')}

Последние коммиты:
{git_info.get('recent_commits', 'Нет коммитов')}
```

### 🤖 **Запущенные процессы:**
```json
{json.dumps(running_processes, indent=2, ensure_ascii=False)}
```

---

## 💻 **КОМАНДЫ ДЛЯ ТЕРМИНАЛА**

### 🔧 **Разработка:**
```bash
{chr(10).join(terminal_commands.get('🔧 Разработка', []))}
```

### 🤖 **Демон синхронизации:**
```bash
{chr(10).join(terminal_commands.get('🤖 Демон синхронизации', []))}
```

### 📊 **Мониторинг:**
```bash
{chr(10).join(terminal_commands.get('📊 Мониторинг', []))}
```

### 🌐 **Веб-интеграция:**
```bash
{chr(10).join(terminal_commands.get('🌐 Веб-интеграция', []))}
```

---

## 📁 **СТРУКТУРА ПРОЕКТА**

### 📂 **Основные файлы ({len(project_structure)} файлов):**
```
{chr(10).join(project_structure[:30])}
{f"... и еще {len(project_structure)-30} файлов" if len(project_structure) > 30 else ""}
```

---

## 🔗 **КЛЮЧЕВЫЕ ССЫЛКИ**

### 🌐 **GitHub Repository:**
https://github.com/Alex-Flok-SAN/fix-prefix_bot

### 📱 **Для веб-версии Claude:**
```
Загрузи контекст FPF Bot проекта:
https://raw.githubusercontent.com/Alex-Flok-SAN/fix-prefix_bot/main/SESSION_CONTEXT_BACKUP.md

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
*🕒 Последнее обновление: {timestamp}*  
*🔗 GitHub: https://github.com/Alex-Flok-SAN/fix-prefix_bot*"""

        # Сохраняем обновленный файл
        self.backup_file.write_text(updated_content, encoding='utf-8')
        
        # Также сохраняем JSON-версию для программного использования
        context_data = {
            "timestamp": timestamp,
            "git_info": git_info,
            "project_structure": project_structure,
            "running_processes": running_processes,
            "key_files": key_files,
            "terminal_commands": terminal_commands
        }
        
        json_backup = self.context_dir / f"context_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(json_backup, 'w', encoding='utf-8') as f:
            json.dump(context_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Контекст сессии сохранен:")
        print(f"📄 Markdown: {self.backup_file}")
        print(f"📋 JSON: {json_backup}")
        
    def create_terminal_alias(self):
        """Создает алиас для быстрого сохранения из терминала"""
        
        alias_script = f"""#!/bin/bash

# 💾 Quick Session Save
# Быстрое сохранение контекста сессии

echo "💾 Сохранение контекста сессии..."
python3 {Path.cwd()}/scripts/save_session_context.py

echo ""
echo "✅ Контекст сохранен в SESSION_CONTEXT_BACKUP.md"
echo "🔗 GitHub: https://github.com/Alex-Flok-SAN/fix-prefix_bot"
echo ""
echo "📱 Для веб-Claude используйте:"
echo "https://raw.githubusercontent.com/Alex-Flok-SAN/fix-prefix_bot/main/SESSION_CONTEXT_BACKUP.md"
"""
        
        alias_path = Path("scripts/save_context.sh")
        alias_path.write_text(alias_script, encoding='utf-8')
        
        # Делаем исполняемым
        subprocess.run(["chmod", "+x", str(alias_path)])
        
        print(f"🔗 Создан быстрый алиас: {alias_path}")
        print("💡 Использование: ./scripts/save_context.sh")

if __name__ == "__main__":
    saver = SessionContextSaver()
    saver.update_backup_file()
    saver.create_terminal_alias()
    
    print("")
    print("🎯 Система сохранения контекста готова!")
    print("📝 Используйте ./scripts/save_context.sh для быстрого сохранения")
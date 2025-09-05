#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🔄 Session Context Restorer
Восстанавливает контекст сессии Claude Code после перезагрузки
"""

import os
import json
import subprocess
from datetime import datetime
from pathlib import Path

class SessionContextRestorer:
    def __init__(self):
        self.backup_file = Path("SESSION_CONTEXT_BACKUP.md")
        self.context_dir = Path("session_context")
        
    def check_system_status(self):
        """Проверяет состояние системы после перезагрузки"""
        print("🔍 Проверка состояния системы...")
        
        status = {}
        
        # Git статус
        try:
            git_result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True
            )
            status["git_changes"] = len(git_result.stdout.strip().split('\n')) if git_result.stdout.strip() else 0
        except Exception:
            status["git_changes"] = "unknown"
        
        # GitHub Sync Daemon
        pid_file = Path(".github_sync_daemon.pid")
        status["sync_daemon"] = "stopped"
        if pid_file.exists():
            try:
                pid = pid_file.read_text().strip()
                check_result = subprocess.run(
                    ["ps", "-p", pid], 
                    capture_output=True, text=True
                )
                status["sync_daemon"] = "running" if check_result.returncode == 0 else "stopped"
            except Exception:
                status["sync_daemon"] = "unknown"
        
        # Claude prompts
        prompts_dir = Path("claude_prompts")
        if prompts_dir.exists():
            status["claude_prompts"] = len(list(prompts_dir.glob("*.txt")))
        else:
            status["claude_prompts"] = 0
        
        return status
    
    def generate_continuation_prompt(self):
        """Генерирует промпт для продолжения работы в Claude Code"""
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = self.check_system_status()
        
        # Читаем последний контекст
        if self.backup_file.exists():
            with open(self.backup_file, 'r', encoding='utf-8') as f:
                backup_preview = f.read()[:1000] + "..."
        else:
            backup_preview = "Файл резервной копии не найден"
        
        continuation_prompt = f"""# 🔄 ВОССТАНОВЛЕНИЕ СЕССИИ FPF BOT - {current_time}

## 📋 **КОНТЕКСТ ВОССТАНОВЛЕНИЯ:**

Это продолжение работы над проектом **FPF Bot** - торговая система для паттерна **FIX-PREFIX-FIX**.

### 🎯 **Загрузи полный контекст из GitHub:**
```
https://raw.githubusercontent.com/Alex-Flok-SAN/fix-prefix_bot/main/SESSION_CONTEXT_BACKUP.md
https://raw.githubusercontent.com/Alex-Flok-SAN/fix-prefix_bot/main/ULTIMATE_KNOWLEDGE_BASE_GUIDE_FOR_AI_TRAINING.md
```

### 📊 **Состояние системы:**
- Git изменений: {status.get('git_changes', 0)}
- Sync Daemon: {status.get('sync_daemon', 'unknown')}
- Claude промптов: {status.get('claude_prompts', 0)}

### 🔧 **Системы проекта:**
✅ **Избирательная синхронизация GitHub** - только утвержденные изменения  
✅ **Веб-интеграция Claude** - доступ к проекту через GitHub  
✅ **Автоматический контекст** - промпты обновляются при изменениях  
✅ **Session Backup** - сохранение состояния сессий  

### ⚡ **Быстрые команды после загрузки контекста:**
```bash
# Проверить статус
git status
./scripts/github_sync_control.sh status

# Обновить промпты
python3 scripts/generate_claude_context.py

# Сохранить текущее состояние
./scripts/save_context.sh

# Синхронизация (если нужна)
./scripts/approved_sync.sh stable "Session restored"
```

### 🎯 **FPF BOT - что это:**
- **Торговый паттерн:** FIX → LOY-FIX → HI-PATTERN → RAY → PREFIX
- **AI детекция:** OCR + pattern recognition
- **Репозиторий:** https://github.com/Alex-Flok-SAN/fix-prefix_bot

## 🚀 **ГОТОВ ПРОДОЛЖИТЬ РАБОТУ!**

После загрузки контекста из GitHub ссылок выше ты будешь знать:
- Полную архитектуру проекта
- Текущее состояние разработки  
- Все системы и скрипты
- Как работать с веб-версией Claude

**Продолжай с того места, где остановились в предыдущей сессии!**

---
*🔄 Автосгенерировано: {current_time}*
*📂 Проект: FPF Bot Trading System*
"""
        
        return continuation_prompt
    
    def create_vscode_task(self):
        """Добавляет VSCode таск для восстановления контекста"""
        
        vscode_dir = Path(".vscode")
        vscode_dir.mkdir(exist_ok=True)
        
        tasks_file = vscode_dir / "tasks.json"
        
        # Читаем существующие задачи или создаем новые
        if tasks_file.exists():
            with open(tasks_file, 'r', encoding='utf-8') as f:
                tasks_data = json.load(f)
        else:
            tasks_data = {
                "version": "2.0.0",
                "tasks": []
            }
        
        # Добавляем задачу восстановления контекста
        restore_task = {
            "label": "🔄 Restore Session Context",
            "type": "shell",
            "command": "python3",
            "args": ["scripts/restore_session_context.py"],
            "group": "build",
            "presentation": {
                "echo": True,
                "reveal": "always",
                "focus": True
            },
            "problemMatcher": []
        }
        
        # Проверяем, есть ли уже такая задача
        existing_task = next((t for t in tasks_data["tasks"] if t.get("label") == "🔄 Restore Session Context"), None)
        if not existing_task:
            tasks_data["tasks"].append(restore_task)
            
            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump(tasks_data, f, indent=4, ensure_ascii=False)
            
            print(f"✅ VSCode задача создана: {tasks_file}")
        else:
            print("ℹ️  VSCode задача уже существует")
    
    def run_restoration(self):
        """Запускает процесс восстановления контекста"""
        
        print("🔄 Запуск восстановления сессии...")
        
        status = self.check_system_status()
        
        print(f"""
📊 **Состояние системы:**
├── Git изменений: {status.get('git_changes', 0)}
├── Sync Daemon: {status.get('sync_daemon', 'stopped')}
└── Claude промптов: {status.get('claude_prompts', 0)}
""")
        
        # Генерируем промпт для продолжения
        continuation_prompt = self.generate_continuation_prompt()
        
        # Сохраняем промпт восстановления
        restore_file = Path("RESTORE_SESSION_PROMPT.md")
        restore_file.write_text(continuation_prompt, encoding='utf-8')
        
        print(f"✅ Промпт восстановления сохранен: {restore_file}")
        
        # Создаем VSCode задачу
        self.create_vscode_task()
        
        # Рекомендации по восстановлению
        print(f"""
🎯 **Рекомендации по восстановлению:**

1️⃣ **Для Claude Code:** Загрузите контекст из:
   📄 {self.backup_file} (если есть)
   📄 {restore_file} (свежий промпт)

2️⃣ **Для веб-Claude:** Используйте GitHub ссылки:
   🔗 https://raw.githubusercontent.com/Alex-Flok-SAN/fix-prefix_bot/main/SESSION_CONTEXT_BACKUP.md

3️⃣ **Проверьте состояние:**
   bash git status
   bash ./scripts/github_sync_control.sh status

4️⃣ **Запустите демон (если нужно):**
   bash ./scripts/github_sync_control.sh start

🚀 Готов продолжить разработку FPF Bot!
""")
        
        # Автоматически запускаем демон, если он остановлен
        if status.get('sync_daemon') == 'stopped':
            print("🤖 Демон остановлен. Запускаю...")
            try:
                subprocess.run(["./scripts/github_sync_control.sh", "start"], check=True)
                print("✅ GitHub Sync Daemon запущен")
            except Exception as e:
                print(f"⚠️  Не удалось запустить демон: {e}")

if __name__ == "__main__":
    restorer = SessionContextRestorer()
    restorer.run_restoration()
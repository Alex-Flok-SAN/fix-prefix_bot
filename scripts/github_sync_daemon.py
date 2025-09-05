#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🔄 GitHub Sync Daemon
Автоматическая система синхронизации знаний с GitHub для веб-версии Claude
"""

import os
import time
import json
import requests
import subprocess
from datetime import datetime
from pathlib import Path

class GitHubSyncDaemon:
    def __init__(self):
        self.repo_owner = "Alex-Flok-SAN"
        self.repo_name = "fix-prefix_bot"
        self.sync_interval = 300  # 5 минут
        self.last_sync = None
        
        # Критические файлы для отслеживания
        self.watched_files = [
            "ULTIMATE_KNOWLEDGE_BASE_GUIDE_FOR_AI_TRAINING.md",
            "baza/01_fpf_pattern.txt",
            "baza/02_philosophy.txt", 
            "core/ai_search_pattern/inference.py",
            "ai/ocr_engine.py"
        ]
        
        self.log_file = Path("logs/github_sync.log")
        self.log_file.parent.mkdir(exist_ok=True)
        
    def log(self, message):
        """Логирование с временными метками"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
    
    def get_repo_info(self):
        """Получает информацию о репозитории через GitHub API"""
        try:
            url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}"
            response = requests.get(url)
            
            if response.status_code == 200:
                return response.json()
            else:
                self.log(f"❌ Ошибка получения информации о репо: {response.status_code}")
                return None
                
        except Exception as e:
            self.log(f"❌ Исключение при запросе к GitHub API: {e}")
            return None
    
    def check_for_updates(self):
        """Проверяет наличие новых коммитов"""
        try:
            # Получаем последний коммит через Git
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            
            if result.returncode == 0:
                current_commit = result.stdout.strip()
                
                # Проверяем, изменился ли коммит
                commit_file = Path("logs/last_commit.txt")
                last_known_commit = ""
                
                if commit_file.exists():
                    last_known_commit = commit_file.read_text().strip()
                
                if current_commit != last_known_commit:
                    self.log(f"🔄 Обнаружены изменения: {current_commit[:8]}")
                    commit_file.write_text(current_commit)
                    return True
                
            return False
            
        except Exception as e:
            self.log(f"❌ Ошибка проверки обновлений: {e}")
            return False
    
    def generate_claude_context(self):
        """Генерирует новый контекст для Claude"""
        try:
            subprocess.run(["python3", "scripts/generate_claude_context.py"], check=True)
            self.log("✅ Контекст для Claude обновлен")
            return True
            
        except Exception as e:
            self.log(f"❌ Ошибка генерации контекста: {e}")
            return False
    
    def notify_changes(self):
        """Уведомляет о новых изменениях"""
        changes_file = Path("claude_prompts/latest_changes.txt")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Получаем информацию о последнем коммите
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--pretty=format:%h - %s (%an, %ar)"],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            
            last_commit_info = result.stdout.strip() if result.returncode == 0 else "Неизвестно"
            
        except Exception:
            last_commit_info = "Ошибка получения информации о коммите"
        
        notification = f"""# 🔄 Обновление FPF Bot - {timestamp}

## 📥 Последние изменения:
{last_commit_info}

## 🌐 Для веб-версии Claude:
Используйте обновленный контекст:

```
Обновись по последним изменениям FPF Bot:
https://raw.githubusercontent.com/{self.repo_owner}/{self.repo_name}/main/ULTIMATE_KNOWLEDGE_BASE_GUIDE_FOR_AI_TRAINING.md

Что нового в проекте?
```

## ⏰ Время обновления: {timestamp}
## 🔗 Репозиторий: https://github.com/{self.repo_owner}/{self.repo_name}

---
*Автоматически сгенерировано GitHub Sync Daemon*
"""
        
        changes_file.write_text(notification, encoding="utf-8")
        self.log(f"📢 Уведомление сохранено: {changes_file}")
    
    def sync_cycle(self):
        """Один цикл синхронизации"""
        self.log("🔄 Начинаю цикл синхронизации...")
        
        if self.check_for_updates():
            self.log("📥 Обнаружены изменения, обновляю контекст...")
            
            if self.generate_claude_context():
                self.notify_changes()
                self.log("✅ Синхронизация завершена успешно")
            else:
                self.log("❌ Ошибка при генерации контекста")
        else:
            self.log("📊 Новых изменений не обнаружено")
    
    def run_daemon(self):
        """Запускает демона синхронизации"""
        self.log(f"🚀 Запуск GitHub Sync Daemon для {self.repo_owner}/{self.repo_name}")
        self.log(f"⏱️  Интервал синхронизации: {self.sync_interval} секунд")
        
        try:
            while True:
                self.sync_cycle()
                time.sleep(self.sync_interval)
                
        except KeyboardInterrupt:
            self.log("🛑 Демон остановлен пользователем")
        except Exception as e:
            self.log(f"💥 Критическая ошибка демона: {e}")
    
    def run_once(self):
        """Запускает одну синхронизацию"""
        self.log("🎯 Разовая синхронизация...")
        self.sync_cycle()

def create_daemon_control_script():
    """Создает скрипт управления демоном"""
    
    control_script = """#!/bin/bash

# 🔄 GitHub Sync Daemon Control Script

DAEMON_PID_FILE=".github_sync_daemon.pid"
DAEMON_SCRIPT="scripts/github_sync_daemon.py"

case "$1" in
    start)
        if [ -f "$DAEMON_PID_FILE" ]; then
            PID=$(cat $DAEMON_PID_FILE)
            if ps -p $PID > /dev/null 2>&1; then
                echo "🟡 Демон уже запущен (PID: $PID)"
                exit 1
            else
                rm -f $DAEMON_PID_FILE
            fi
        fi
        
        echo "🚀 Запуск GitHub Sync Daemon..."
        nohup python3 $DAEMON_SCRIPT > logs/github_sync_daemon.out 2>&1 &
        echo $! > $DAEMON_PID_FILE
        echo "✅ Демон запущен (PID: $!)"
        ;;
        
    stop)
        if [ -f "$DAEMON_PID_FILE" ]; then
            PID=$(cat $DAEMON_PID_FILE)
            if ps -p $PID > /dev/null 2>&1; then
                kill $PID
                rm -f $DAEMON_PID_FILE
                echo "🛑 Демон остановлен"
            else
                rm -f $DAEMON_PID_FILE
                echo "⚠️  Демон не был запущен"
            fi
        else
            echo "❌ PID файл не найден"
        fi
        ;;
        
    status)
        if [ -f "$DAEMON_PID_FILE" ]; then
            PID=$(cat $DAEMON_PID_FILE)
            if ps -p $PID > /dev/null 2>&1; then
                echo "🟢 Демон запущен (PID: $PID)"
            else
                echo "🔴 Демон не отвечает (PID файл найден, но процесс не найден)"
                rm -f $DAEMON_PID_FILE
            fi
        else
            echo "🔴 Демон не запущен"
        fi
        ;;
        
    sync)
        echo "🔄 Принудительная синхронизация..."
        python3 $DAEMON_SCRIPT --once
        ;;
        
    *)
        echo "Использование: $0 {start|stop|status|sync}"
        echo ""
        echo "Команды:"
        echo "  start  - Запустить демон синхронизации"
        echo "  stop   - Остановить демон"  
        echo "  status - Проверить статус демона"
        echo "  sync   - Принудительная разовая синхронизация"
        exit 1
        ;;
esac
"""
    
    control_path = Path("scripts/github_sync_control.sh")
    control_path.write_text(control_script, encoding="utf-8")
    
    # Делаем скрипт исполняемым
    subprocess.run(["chmod", "+x", str(control_path)])
    
    print(f"✅ Скрипт управления создан: {control_path}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # Разовая синхронизация
        daemon = GitHubSyncDaemon()
        daemon.run_once()
    else:
        # Постоянный демон
        daemon = GitHubSyncDaemon() 
        daemon.run_daemon()
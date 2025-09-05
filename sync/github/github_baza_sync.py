#!/usr/bin/env python3
"""
GitHub Issues как система управления базой знаний
Синхронизация между всеми версиями Claude через Issues API
"""

import requests
import json
from datetime import datetime
from pathlib import Path
import hashlib
import time

class GitHubBazaSync:
    def __init__(self, token, repo_owner, repo_name):
        self.token = token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # ID специального Issue для базы знаний
        self.baza_issue_id = None
        self.local_baza_path = Path("baza.txt")
    
    def find_or_create_baza_issue(self):
        """Найти или создать специальный Issue для базы знаний"""
        # Ищем Issue с меткой "baza-knowledge"
        url = f"{self.base_url}/issues"
        params = {"labels": "baza-knowledge", "state": "open"}
        
        response = requests.get(url, headers=self.headers, params=params)
        if response.status_code != 200:
            print(f"❌ Ошибка доступа к GitHub API: {response.status_code}")
            return None
            
        issues = response.json()
        
        if issues:
            self.baza_issue_id = issues[0]["number"]
            print(f"✅ Найден Issue #{self.baza_issue_id} для базы знаний")
            return issues[0]
        else:
            # Создаем новый Issue
            return self.create_baza_issue()
    
    def create_baza_issue(self):
        """Создать новый Issue для базы знаний"""
        url = f"{self.base_url}/issues"
        
        initial_content = self.load_local_baza() or "# База знаний FPF Bot\n\n*Файл пуст*"
        
        data = {
            "title": "📚 База знаний FPF Bot [AUTO-SYNC]",
            "body": f"""# 🤖 Автосинхронизируемая база знаний

**Назначение:** Этот Issue служит центральным хранилищем базы знаний проекта.

**Как работает:**
- Любое изменение в комментариях автоматически синхронизируется с локальным файлом
- Claude может читать и обновлять содержимое через все платформы
- История изменений сохраняется в комментариях

**Инструкции для Claude:**
1. Для добавления ЛОГИКИ: добавьте комментарий с новыми идеями
2. Для ПРОСМОТРА базы: читайте последний комментарий с базой
3. Система автоматически синхронизирует изменения

---

## 📄 ТЕКУЩАЯ ВЕРСИЯ БАЗЫ:

```
{initial_content}
```

---

*Последнее обновление: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
""",
            "labels": ["baza-knowledge", "auto-sync", "documentation"]
        }
        
        response = requests.post(url, headers=self.headers, json=data)
        if response.status_code != 201:
            print(f"❌ Ошибка создания Issue: {response.status_code}")
            return None
            
        issue = response.json()
        self.baza_issue_id = issue["number"]
        print(f"✅ Создан Issue #{self.baza_issue_id} для базы знаний")
        return issue
    
    def load_local_baza(self):
        """Загрузить локальную базу знаний"""
        try:
            if self.local_baza_path.exists():
                return self.local_baza_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"⚠️ Ошибка чтения локального файла: {e}")
        return None
    
    def save_local_baza(self, content):
        """Сохранить базу знаний локально"""
        try:
            self.local_baza_path.write_text(content, encoding='utf-8')
            print(f"💾 Локальная база обновлена: {self.local_baza_path}")
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")
            return False
    
    def get_content_hash(self, content):
        """Получить хеш содержимого для сравнения"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def update_issue_with_baza(self, new_content, source="local"):
        """Обновить Issue новым содержимым базы"""
        if not self.baza_issue_id:
            self.find_or_create_baza_issue()
        
        # Добавляем комментарий с новым содержимым
        url = f"{self.base_url}/issues/{self.baza_issue_id}/comments"
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        content_hash = self.get_content_hash(new_content)
        
        comment_body = f"""## 🔄 Обновление базы знаний

**Источник:** {source}  
**Время:** {timestamp}  
**Хеш:** `{content_hash}`

```
{new_content}
```

---
*Автоматически синхронизировано*
"""
        
        data = {"body": comment_body}
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code == 201:
            print(f"✅ База обновлена в Issue #{self.baza_issue_id}")
            return True
        else:
            print(f"❌ Ошибка обновления Issue: {response.status_code}")
            return False
    
    def get_latest_baza_from_issue(self):
        """Получить последнюю версию базы из Issue"""
        if not self.baza_issue_id:
            issue = self.find_or_create_baza_issue()
            if not issue:
                return None
        
        # Получаем комментарии к Issue
        url = f"{self.base_url}/issues/{self.baza_issue_id}/comments"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            print(f"❌ Ошибка получения комментариев: {response.status_code}")
            return None
            
        comments = response.json()
        
        if not comments:
            return None
        
        # Ищем последний комментарий с базой знаний
        for comment in reversed(comments):
            body = comment["body"]
            if "```" in body and "🔄 Обновление базы знаний" in body:
                # Извлекаем содержимое из code block
                lines = body.split('\n')
                in_code_block = False
                content_lines = []
                
                for line in lines:
                    if line.strip() == "```" and not in_code_block:
                        in_code_block = True
                        continue
                    elif line.strip() == "```" and in_code_block:
                        break
                    elif in_code_block:
                        content_lines.append(line)
                
                if content_lines:
                    return '\n'.join(content_lines)
        
        return None
    
    def sync_from_issue_to_local(self):
        """Синхронизировать базу из Issue в локальный файл"""
        print("📥 Синхронизация Issue → Локальный файл...")
        latest_content = self.get_latest_baza_from_issue()
        
        if latest_content:
            local_content = self.load_local_baza()
            
            if latest_content != local_content:
                if self.save_local_baza(latest_content):
                    print("✅ База синхронизирована из Issue в локальный файл")
                    return True
            else:
                print("ℹ️ Локальная база уже актуальна")
        else:
            print("⚠️ Не удалось получить данные из Issue")
        
        return False
    
    def sync_from_local_to_issue(self):
        """Синхронизировать базу из локального файла в Issue"""
        print("📤 Синхронизация Локальный файл → Issue...")
        local_content = self.load_local_baza()
        
        if local_content:
            latest_issue_content = self.get_latest_baza_from_issue()
            
            if local_content != latest_issue_content:
                if self.update_issue_with_baza(local_content, "local"):
                    print("✅ База синхронизирована из локального файла в Issue")
                    return True
            else:
                print("ℹ️ Issue уже содержит актуальную базу")
        else:
            print("⚠️ Локальный файл базы не найден")
        
        return False
    
    def get_issue_url(self):
        """Получить URL Issue с базой знаний"""
        if self.baza_issue_id:
            return f"https://github.com/{self.repo_owner}/{self.repo_name}/issues/{self.baza_issue_id}"
        return None

# Демон автосинхронизации
class GitHubBazaSyncDaemon:
    def __init__(self, sync_manager, check_interval=30):
        self.sync = sync_manager
        self.check_interval = check_interval
        self.last_local_hash = ""
        self.last_issue_hash = ""
        
    def run(self):
        """Запуск демона синхронизации"""
        print(f"🔄 Запуск демона GitHub синхронизации (интервал: {self.check_interval}с)")
        
        if not self.sync.find_or_create_baza_issue():
            print("❌ Не удалось инициализировать Issue для синхронизации")
            return
        
        print(f"🔗 Issue URL: {self.sync.get_issue_url()}")
        
        try:
            while True:
                self.check_and_sync()
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print("\n🛑 Демон остановлен пользователем")
        except Exception as e:
            print(f"💥 Критическая ошибка: {e}")
    
    def check_and_sync(self):
        """Проверка и синхронизация изменений"""
        # Проверяем локальные изменения
        local_content = self.sync.load_local_baza()
        if local_content:
            current_local_hash = self.sync.get_content_hash(local_content)
            if current_local_hash != self.last_local_hash:
                print("📝 Обнаружены локальные изменения")
                self.sync.sync_from_local_to_issue()
                self.last_local_hash = current_local_hash
        
        # Проверяем изменения в Issue
        issue_content = self.sync.get_latest_baza_from_issue()
        if issue_content:
            current_issue_hash = self.sync.get_content_hash(issue_content)
            if current_issue_hash != self.last_issue_hash:
                print("🌐 Обнаружены изменения в Issue")
                self.sync.sync_from_issue_to_local()
                self.last_issue_hash = current_issue_hash

# Загрузка токена из переменной окружения
def load_github_token():
    """Загрузить GitHub токен из .env файла или переменной окружения"""
    import os
    
    # Пробуем загрузить из .env файла
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().split('\n'):
            if line.startswith("GITHUB_TOKEN="):
                return line.split('=', 1)[1].strip()
    
    # Пробуем загрузить из переменной окружения
    token = os.getenv('GITHUB_TOKEN')
    if token:
        return token
    
    print("❌ GitHub токен не найден!")
    print("💡 Создайте токен: https://github.com/settings/tokens")
    print("💡 Добавьте в .env файл: GITHUB_TOKEN=ваш_токен")
    print("💡 Или запустите: python3 setup_github_sync.py")
    return None

# Пример использования
if __name__ == "__main__":
    GITHUB_TOKEN = load_github_token()
    if not GITHUB_TOKEN:
        print("❌ Запуск невозможен без токена")
        exit(1)
    
    REPO_OWNER = "Alex-Flok-SAN"
    REPO_NAME = "fpf-bot"
    
    sync = GitHubBazaSync(GITHUB_TOKEN, REPO_OWNER, REPO_NAME)
    
    print("🚀 Инициализация GitHub синхронизации базы знаний...")
    
    # Первичная настройка
    if not sync.find_or_create_baza_issue():
        print("❌ Ошибка инициализации Issue")
        exit(1)
    
    print(f"🔗 Issue URL: {sync.get_issue_url()}")
    
    # Синхронизация
    print("\n📤 Синхронизация локальной базы с Issue...")
    sync.sync_from_local_to_issue()  # Локальный → Issue
    
    print("\n📥 Обратная синхронизация для проверки...")
    sync.sync_from_issue_to_local()  # Issue → Локальный
    
    print("\n✅ Система готова к работе!")
    print("💡 Для автоматической синхронизации запустите:")
    print("   python3 -c \"from github_baza_sync import *; daemon = GitHubBazaSyncDaemon(GitHubBazaSync(load_github_token(), 'Alex-Flok-SAN', 'fpf-bot')); daemon.run()\"")
    print("💡 Или используйте: python3 setup_github_sync.py")
#!/usr/bin/env python3
"""
Система синхронизации baza.txt через GitHub Gist
Работает с любой версией Claude через публичные raw ссылки и GitHub API
"""

import requests
import json
import time
import hashlib
from pathlib import Path
import logging
from datetime import datetime
import os

class GistBazaSync:
    def __init__(self, gist_id, github_token=None):
        self.gist_id = gist_id
        self.github_token = github_token
        # Project paths
        self.project_root = Path(__file__).parent.parent.parent
        self.local_file = self.project_root / "baza.txt"
        
        # GitHub API endpoints
        self.api_url = f"https://api.github.com/gists/{gist_id}"
        self.raw_url = f"https://gist.githubusercontent.com/Alex-Flok-SAN/{gist_id}/raw"
        
        # Headers для API
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'FPF-Bot-Sync'
        }
        
        if github_token:
            self.headers['Authorization'] = f'token {github_token}'
        
        # Для отслеживания изменений
        self.last_remote_hash = ""
        self.last_local_hash = ""
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def get_gist_info(self):
        """Получить информацию о Gist"""
        try:
            response = requests.get(self.api_url, headers=self.headers)
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Ошибка получения Gist: {response.text}")
                return None
        except Exception as e:
            self.logger.error(f"Ошибка API: {e}")
            return None
    
    def read_remote_baza(self):
        """Читает базу из Gist (через raw URL)"""
        try:
            # Используем raw URL для чтения (работает без токена)
            response = requests.get(f"{self.raw_url}/gistfile1.txt")
            if response.status_code == 200:
                return response.text
            else:
                # Если не получилось через raw, пробуем через API
                gist_info = self.get_gist_info()
                if gist_info and 'files' in gist_info:
                    files = gist_info['files']
                    # Ищем первый текстовый файл
                    for filename, file_data in files.items():
                        if file_data.get('content'):
                            return file_data['content']
                self.logger.error(f"Не удалось прочитать Gist")
                return None
        except Exception as e:
            self.logger.error(f"Ошибка чтения Gist: {e}")
            return None
    
    def read_local_baza(self):
        """Читает локальную базу"""
        try:
            if self.local_file.exists():
                return self.local_file.read_text(encoding='utf-8')
        except Exception as e:
            self.logger.error(f"Ошибка чтения локального файла: {e}")
        return ""
    
    def save_local_baza(self, content):
        """Сохраняет базу локально"""
        try:
            self.local_file.write_text(content, encoding='utf-8')
            self.logger.info(f"✅ Локальная база обновлена: {datetime.now()}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка сохранения: {e}")
            return False
    
    def update_gist(self, content, filename="gistfile1.txt"):
        """Обновляет Gist новым содержимым"""
        if not self.github_token:
            self.logger.error("❌ Нужен GitHub токен для обновления Gist")
            return False
        
        data = {
            "description": f"FPF Bot Knowledge Base - updated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "files": {
                filename: {
                    "content": content
                }
            }
        }
        
        try:
            response = requests.patch(self.api_url, 
                                    json=data, headers=self.headers)
            if response.status_code == 200:
                self.logger.info(f"✅ Gist обновлен: {datetime.now()}")
                return True
            else:
                self.logger.error(f"Ошибка обновления Gist: {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Ошибка обновления Gist: {e}")
            return False
    
    def get_content_hash(self, content):
        """Получить хеш содержимого"""
        return hashlib.md5(content.encode('utf-8')).hexdigest() if content else ""
    
    def sync_remote_to_local(self):
        """Синхронизация Gist → Local"""
        remote_content = self.read_remote_baza()
        if remote_content is None:
            return False
        
        local_content = self.read_local_baza()
        
        if remote_content != local_content:
            if self.save_local_baza(remote_content):
                self.logger.info("🔄 Синхронизировано: Gist → Local")
                return True
        return False
    
    def sync_local_to_remote(self):
        """Синхронизация Local → Gist"""
        local_content = self.read_local_baza()
        if not local_content:
            return False
        
        remote_content = self.read_remote_baza()
        
        if local_content != remote_content:
            if self.update_gist(local_content):
                self.logger.info("🔄 Синхронизировано: Local → Gist")
                return True
        return False
    
    def auto_sync_daemon(self, interval=30):
        """Автоматическая синхронизация каждые N секунд"""
        self.logger.info(f"🚀 Запуск автосинхронизации Gist (интервал: {interval}с)")
        self.logger.info(f"🔗 Gist URL: https://gist.github.com/Alex-Flok-SAN/{self.gist_id}")
        
        try:
            while True:
                # Проверяем изменения
                remote_content = self.read_remote_baza()
                local_content = self.read_local_baza()
                
                if remote_content is not None:
                    remote_hash = self.get_content_hash(remote_content)
                    local_hash = self.get_content_hash(local_content)
                    
                    # Синхронизируем при изменениях
                    if remote_hash != self.last_remote_hash and remote_hash != local_hash:
                        self.sync_remote_to_local()
                        
                    if local_hash != self.last_local_hash and local_hash != remote_hash:
                        self.sync_local_to_remote()
                    
                    # Обновляем хеши
                    self.last_remote_hash = remote_hash
                    self.last_local_hash = local_hash
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Автосинхронизация остановлена")
    
    def get_public_urls(self):
        """Получить публичные URL для доступа"""
        return {
            'raw_url': f"{self.raw_url}/gistfile1.txt",
            'gist_url': f"https://gist.github.com/Alex-Flok-SAN/{self.gist_id}",
            'gist_id': self.gist_id
        }

# Загрузка конфигурации из .env
def load_gist_config():
    """Загрузить конфигурацию Gist из .env"""
    env_path = Path(".env")
    config = {}
    
    # Пробуем загрузить из .env файла
    if env_path.exists():
        for line in env_path.read_text().split('\n'):
            if line.startswith("GIST_ID="):
                config['gist_id'] = line.split('=', 1)[1].strip()
            elif line.startswith("GITHUB_TOKEN="):
                config['github_token'] = line.split('=', 1)[1].strip()
    
    # Пробуем загрузить из переменных окружения
    config['gist_id'] = config.get('gist_id') or os.getenv('GIST_ID')
    config['github_token'] = config.get('github_token') or os.getenv('GITHUB_TOKEN')
    
    return config

# Команды для управления
if __name__ == "__main__":
    import sys
    
    # Загружаем конфигурацию
    config = load_gist_config()
    
    GIST_ID = config.get('gist_id')
    GITHUB_TOKEN = config.get('github_token')
    
    if not GIST_ID:
        print("❌ GIST_ID не настроен в .env")
        print("💡 Добавьте: GIST_ID=your_gist_id")
        sys.exit(1)
    
    sync = GistBazaSync(GIST_ID, GITHUB_TOKEN)
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "pull":
            # Загрузить из Gist в локальный файл
            sync.sync_remote_to_local()
            
        elif command == "push":
            # Отправить локальный файл в Gist
            if not GITHUB_TOKEN:
                print("❌ Нужен GITHUB_TOKEN для обновления Gist")
            else:
                sync.sync_local_to_remote()
                
        elif command == "daemon":
            # Запустить автосинхронизацию
            sync.auto_sync_daemon()
                
        elif command == "check":
            # Проверить различия
            remote = sync.read_remote_baza()
            local = sync.read_local_baza()
            
            if remote is not None and local and remote != local:
                print("⚠️ Файлы различаются")
                print(f"Remote: '{remote[:50]}...'")
                print(f"Local: '{local[:50]}...'")
                print(f"Remote hash: {sync.get_content_hash(remote)}")
                print(f"Local hash: {sync.get_content_hash(local)}")
            else:
                print("✅ Файлы синхронизированы")
                    
        elif command == "info":
            # Показать информацию о Gist
            urls = sync.get_public_urls()
            print(f"📋 Информация о Gist:")
            print(f"🆔 Gist ID: {GIST_ID}")
            print(f"📄 Raw URL: {urls['raw_url']}")
            print(f"🌐 Gist URL: {urls['gist_url']}")
            
        elif command == "test":
            # Тест обновления Gist
            print("🧪 Тестирование обновления Gist...")
            local_content = sync.read_local_baza()
            print(f"Содержимое для отправки: '{local_content}'")
            
            if sync.update_gist(local_content):
                print("✅ Gist успешно обновлен!")
                urls = sync.get_public_urls()
                print(f"🔗 Проверьте: {urls['raw_url']}")
            else:
                print("❌ Ошибка обновления Gist")
    else:
        print("Использование:")
        print("  python gist_sync.py pull    - загрузить из Gist")
        print("  python gist_sync.py push    - отправить в Gist")
        print("  python gist_sync.py daemon  - автосинхронизация")
        print("  python gist_sync.py check   - проверить синхронизацию")
        print("  python gist_sync.py info    - информация о Gist")
        print("  python gist_sync.py test    - тест обновления Gist")
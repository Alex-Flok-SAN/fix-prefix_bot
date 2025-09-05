#!/usr/bin/env python3
"""
Автосинхронизация базы знаний FPF Bot с GitHub
Команда: "обнови базу" - автоматически обновляет репозиторий с изменениями
"""

import subprocess
import os
import json
from datetime import datetime
from pathlib import Path

class KnowledgeBaseSync:
    def __init__(self):
        self.project_root = Path("/Users/sashaflok/fpf_bot")
        self.baza_path = self.project_root / "baza"
        self.repo_url = "https://github.com/Alex-Flok-SAN/-tmp-fpf-bot-knowledge-base-.git"
        self.temp_repo = Path("/tmp/fpf-knowledge-sync")
        
    def sync_to_github(self, commit_message=None):
        """Синхронизирует локальную базу с GitHub"""
        
        # Стандартное сообщение если не указано
        if not commit_message:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            commit_message = f"📚 Knowledge base update - {timestamp}"
            
        try:
            print("🔄 Начинаем синхронизацию базы знаний...")
            
            # Шаг 1: Клонируем репозиторий
            self._clone_repo()
            
            # Шаг 2: Копируем обновленные файлы
            self._copy_updated_files()
            
            # Шаг 3: Коммитим и пушим изменения
            self._commit_and_push(commit_message)
            
            # Шаг 4: Очистка
            self._cleanup()
            
            print("✅ База знаний успешно обновлена на GitHub!")
            print(f"🔗 {self.repo_url.replace('.git', '')}")
            
        except Exception as e:
            print(f"❌ Ошибка синхронизации: {e}")
            self._cleanup()
            raise
            
    def _clone_repo(self):
        """Клонирует репозиторий"""
        print("📥 Клонирование репозитория...")
        
        # Удаляем старую папку если есть
        if self.temp_repo.exists():
            subprocess.run(["rm", "-rf", str(self.temp_repo)], check=True)
            
        # Клонируем
        subprocess.run([
            "git", "clone", self.repo_url, str(self.temp_repo)
        ], check=True, capture_output=True)
        
    def _copy_updated_files(self):
        """Копирует обновленные файлы базы знаний"""
        print("📋 Копирование обновленных файлов...")
        
        # Копируем папку baza
        subprocess.run([
            "cp", "-r", str(self.baza_path), str(self.temp_repo / "baza")
        ], check=True)
        
        # Копируем PROJECT_STRUCTURE.md если есть
        project_structure = self.project_root / "PROJECT_STRUCTURE.md"
        if project_structure.exists():
            subprocess.run([
                "cp", str(project_structure), str(self.temp_repo)
            ], check=True)
            
        # Обновляем README с новой датой
        self._update_readme()
        
    def _update_readme(self):
        """Обновляет README с текущей датой"""
        readme_path = self.temp_repo / "README.md"
        if readme_path.exists():
            content = readme_path.read_text()
            
            # Обновляем дату в конце файла
            current_date = datetime.now().strftime('%Y-%m-%d')
            updated_content = content.replace(
                "*Последнее обновление: $(date '+%Y-%m-%d')*",
                f"*Последнее обновление: {current_date}*"
            )
            
            # Если старый формат даты, заменяем
            import re
            updated_content = re.sub(
                r'\*Последнее обновление: \d{4}-\d{2}-\d{2}\*',
                f"*Последнее обновление: {current_date}*",
                updated_content
            )
            
            readme_path.write_text(updated_content)
            
    def _commit_and_push(self, message):
        """Коммитит и пушит изменения"""
        print("📤 Коммит и загрузка изменений...")
        
        # Переходим в папку репозитория
        os.chdir(str(self.temp_repo))
        
        # Добавляем все изменения
        subprocess.run(["git", "add", "."], check=True)
        
        # Проверяем есть ли изменения
        result = subprocess.run(
            ["git", "diff", "--staged", "--quiet"], 
            capture_output=True
        )
        
        if result.returncode == 0:
            print("ℹ️ Нет изменений для коммита")
            return
            
        # Коммитим
        full_message = f"""{message}

🚀 Generated with Claude Code
https://claude.ai/code

Co-Authored-By: Claude <noreply@anthropic.com>"""
        
        subprocess.run([
            "git", "commit", "-m", full_message
        ], check=True)
        
        # Пушим
        subprocess.run(["git", "push"], check=True)
        
    def _cleanup(self):
        """Очищает временные файлы"""
        if self.temp_repo.exists():
            subprocess.run(["rm", "-rf", str(self.temp_repo)], check=False)
            
    def get_changes_summary(self):
        """Возвращает краткое описание изменений в базе"""
        changes = []
        
        # Проверяем какие файлы были изменены недавно
        import time
        cutoff_time = time.time() - (24 * 60 * 60)  # последние 24 часа
        
        for file_path in self.baza_path.glob("*.txt"):
            if file_path.stat().st_mtime > cutoff_time:
                changes.append(f"- {file_path.name}")
                
        return changes


def main():
    """Основная функция для командной строки"""
    import sys
    
    sync = KnowledgeBaseSync()
    
    if len(sys.argv) > 1:
        # Объединяем все аргументы в сообщение коммита
        commit_message = " ".join(sys.argv[1:])
        sync.sync_to_github(commit_message)
    else:
        # Показываем недавние изменения и спрашиваем подтверждение
        changes = sync.get_changes_summary()
        
        if changes:
            print("📝 Обнаружены изменения в файлах:")
            for change in changes:
                print(f"  {change}")
        else:
            print("ℹ️ Изменения не обнаружены за последние 24 часа")
            
        # Синхронизируем в любом случае
        confirm = input("\n🤔 Синхронизировать базу знаний с GitHub? (y/n): ")
        if confirm.lower() in ['y', 'yes', 'да', 'д', '']:
            sync.sync_to_github()
        else:
            print("❌ Синхронизация отменена")


if __name__ == "__main__":
    main()
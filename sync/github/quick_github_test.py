#!/usr/bin/env python3
"""
Быстрый тест GitHub синхронизации (без сохранения токена)
"""

import sys
from github_baza_sync import GitHubBazaSync

def main():
    print("🚀 Быстрый тест GitHub синхронизации базы знаний")
    print("=" * 50)
    
    # Запрашиваем токен для разового использования
    print("Для тестирования нужен GitHub Personal Access Token")
    print("(токен НЕ будет сохранен)")
    token = input("Введите токен: ").strip()
    
    if not token:
        print("❌ Токен не может быть пустым")
        return
    
    # Создаем менеджер синхронизации
    sync = GitHubBazaSync(token, "Alex-Flok-SAN", "fpf-bot")
    
    print("\n1. 🔍 Поиск или создание Issue для базы знаний...")
    issue = sync.find_or_create_baza_issue()
    
    if not issue:
        print("❌ Не удалось создать или найти Issue")
        return
    
    print(f"✅ Issue готов: {sync.get_issue_url()}")
    
    print("\n2. 📤 Синхронизация baza.txt → GitHub Issue...")
    if sync.sync_from_local_to_issue():
        print("✅ База успешно загружена в Issue")
    else:
        print("⚠️ Проблемы с синхронизацией")
    
    print(f"\n🎉 Готово! Теперь любая версия Claude может работать с базой через:")
    print(f"🔗 {sync.get_issue_url()}")
    print("\nДля постоянного использования запустите setup_github_sync.py")

if __name__ == "__main__":
    main()
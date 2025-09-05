#!/usr/bin/env python3
"""
Скрипт для настройки и тестирования GitHub синхронизации базы знаний
"""

import os
import sys
from pathlib import Path
from github_baza_sync import GitHubBazaSync, GitHubBazaSyncDaemon

def setup_token():
    """Настройка GitHub токена"""
    print("🔑 Настройка GitHub токена для синхронизации")
    print("\nДля работы системы нужен GitHub Personal Access Token:")
    print("1. Перейдите в https://github.com/settings/tokens")
    print("2. Нажмите 'Generate new token (classic)'")
    print("3. Выберите срок действия и права доступа:")
    print("   - repo (полный доступ к репозиториям)")
    print("   - write:discussion (для создания Issues)")
    print("4. Скопируйте созданный токен")
    print()
    
    token = input("Введите ваш GitHub токен: ").strip()
    if not token:
        print("❌ Токен не может быть пустым")
        return None
    
    # Сохраняем токен в .env файл
    env_path = Path(".env")
    env_content = ""
    
    if env_path.exists():
        env_content = env_path.read_text()
    
    # Обновляем или добавляем токен
    lines = env_content.split('\n')
    token_line = f"GITHUB_TOKEN={token}"
    
    token_found = False
    for i, line in enumerate(lines):
        if line.startswith("GITHUB_TOKEN="):
            lines[i] = token_line
            token_found = True
            break
    
    if not token_found:
        lines.append(token_line)
    
    env_path.write_text('\n'.join(lines))
    print("✅ Токен сохранен в .env файл")
    return token

def load_token():
    """Загрузка токена из .env"""
    env_path = Path(".env")
    if not env_path.exists():
        return None
    
    for line in env_path.read_text().split('\n'):
        if line.startswith("GITHUB_TOKEN="):
            return line.split('=', 1)[1].strip()
    return None

def test_sync_system():
    """Тестирование системы синхронизации"""
    print("🧪 Тестирование системы синхронизации...")
    
    # Загружаем токен
    token = load_token()
    if not token:
        token = setup_token()
        if not token:
            print("❌ Не удалось получить токен")
            return False
    
    # Создаем менеджер синхронизации
    sync = GitHubBazaSync(token, "Alex-Flok-SAN", "fpf-bot")
    
    # Тест 1: Создание/поиск Issue
    print("\n📋 Тест 1: Поиск или создание Issue для базы знаний...")
    issue = sync.find_or_create_baza_issue()
    if not issue:
        print("❌ Не удалось создать или найти Issue")
        return False
    
    print(f"🔗 URL Issue: {sync.get_issue_url()}")
    
    # Тест 2: Синхронизация из локального файла в Issue
    print("\n📤 Тест 2: Синхронизация baza.txt → GitHub Issue...")
    if sync.sync_from_local_to_issue():
        print("✅ Локальная база успешно синхронизирована в Issue")
    else:
        print("⚠️ Возможные проблемы с синхронизацией в Issue")
    
    # Тест 3: Обратная синхронизация
    print("\n📥 Тест 3: Синхронизация GitHub Issue → локальный файл...")
    if sync.sync_from_issue_to_local():
        print("✅ База из Issue успешно синхронизирована локально")
    else:
        print("ℹ️ Локальная база уже актуальна")
    
    print("\n🎉 Система синхронизации настроена и протестирована!")
    print(f"🔗 Ваш Issue для базы знаний: {sync.get_issue_url()}")
    
    return True

def start_daemon():
    """Запуск демона синхронизации"""
    print("🤖 Запуск демона автосинхронизации...")
    
    token = load_token()
    if not token:
        print("❌ GitHub токен не настроен. Запустите сначала тестирование.")
        return
    
    sync = GitHubBazaSync(token, "Alex-Flok-SAN", "fpf-bot")
    daemon = GitHubBazaSyncDaemon(sync, check_interval=30)
    
    try:
        daemon.run()
    except KeyboardInterrupt:
        print("\n🛑 Демон остановлен")

def main():
    """Главное меню"""
    print("=" * 60)
    print("🚀 GitHub База Знаний - Система Синхронизации")
    print("=" * 60)
    
    while True:
        print("\nВыберите действие:")
        print("1. 🔑 Настроить GitHub токен")
        print("2. 🧪 Тестировать систему синхронизации")
        print("3. 🤖 Запустить демон автосинхронизации")
        print("4. ℹ️  Показать статус")
        print("5. 🚪 Выйти")
        
        choice = input("\nВаш выбор (1-5): ").strip()
        
        if choice == "1":
            setup_token()
        elif choice == "2":
            test_sync_system()
        elif choice == "3":
            start_daemon()
        elif choice == "4":
            show_status()
        elif choice == "5":
            print("👋 До свидания!")
            break
        else:
            print("❌ Неверный выбор")

def show_status():
    """Показать статус системы"""
    print("\n📊 Статус системы:")
    
    # Проверяем токен
    token = load_token()
    if token:
        print("✅ GitHub токен: Настроен")
    else:
        print("❌ GitHub токен: Не настроен")
    
    # Проверяем локальную базу
    baza_path = Path("baza.txt")
    if baza_path.exists():
        size = len(baza_path.read_text(encoding='utf-8'))
        print(f"✅ Локальная база: {size} символов")
    else:
        print("❌ Локальная база: Не найдена")
    
    # Проверяем подключение к GitHub
    if token:
        try:
            sync = GitHubBazaSync(token, "Alex-Flok-SAN", "fpf-bot")
            issue = sync.find_or_create_baza_issue()
            if issue:
                print(f"✅ GitHub Issue: #{sync.baza_issue_id}")
                print(f"🔗 URL: {sync.get_issue_url()}")
            else:
                print("❌ GitHub Issue: Ошибка подключения")
        except Exception as e:
            print(f"❌ GitHub подключение: {e}")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Простой запуск системы синхронизации GitHub Issues
"""

import sys
import os
from pathlib import Path

def main():
    print("🚀 FPF Bot - Система синхронизации базы знаний")
    print("=" * 50)
    
    # Проверяем токен
    token_found = False
    
    # Проверка .env файла
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().split('\n'):
            if line.startswith("GITHUB_TOKEN=") and line.split('=', 1)[1].strip():
                token_found = True
                break
    
    # Проверка переменной окружения
    if not token_found and os.getenv('GITHUB_TOKEN'):
        token_found = True
    
    if not token_found:
        print("❌ GitHub токен не настроен")
        print("\n📋 Варианты настройки:")
        print("1. Создать .env файл с GITHUB_TOKEN=ваш_токен")
        print("2. Запустить python3 setup_github_sync.py (полная настройка)")
        print("3. Запустить python3 quick_github_test.py (быстрый тест)")
        print("\n💡 Токен создается здесь: https://github.com/settings/tokens")
        print("   Нужны права: repo, issues")
        return
    
    print("✅ GitHub токен найден")
    
    # Запускаем основной скрипт
    print("\n🔄 Запуск синхронизации...")
    os.system("python3 github_baza_sync.py")

if __name__ == "__main__":
    main()
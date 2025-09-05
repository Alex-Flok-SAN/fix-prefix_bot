#!/usr/bin/env python3
"""
Настройка Telegram бота для управления базой знаний
"""

import os
from pathlib import Path

def create_env_template():
    """Создает шаблон .env файла для бота"""
    env_path = Path(".env")
    
    # Читаем существующий .env
    existing_vars = {}
    if env_path.exists():
        for line in env_path.read_text().split('\n'):
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                existing_vars[key] = value
    
    # Добавляем переменные для бота если их нет
    new_vars = {}
    
    if 'TELEGRAM_BOT_TOKEN' not in existing_vars:
        print("🤖 Настройка Telegram Bot")
        print("1. Создайте бота у @BotFather в Telegram")
        print("2. Получите токен бота")
        bot_token = input("Введите токен Telegram бота: ").strip()
        if bot_token:
            new_vars['TELEGRAM_BOT_TOKEN'] = bot_token
    
    if 'AUTHORIZED_USER_IDS' not in existing_vars:
        print("\n👥 Настройка авторизованных пользователей")
        print("Найдите ваш User ID:")
        print("- Напишите @userinfobot в Telegram")
        print("- Или @raw_data_bot")
        user_ids = input("Введите User ID (через запятую если несколько): ").strip()
        if user_ids:
            new_vars['AUTHORIZED_USER_IDS'] = user_ids
    
    # Сохраняем обновленный .env
    if new_vars:
        all_vars = {**existing_vars, **new_vars}
        
        env_content = []
        for key, value in all_vars.items():
            env_content.append(f"{key}={value}")
        
        env_path.write_text('\n'.join(env_content) + '\n')
        print(f"✅ Конфигурация сохранена в {env_path}")
        
        print("\n📋 Добавленные переменные:")
        for key, value in new_vars.items():
            masked_value = value[:10] + "..." if len(value) > 10 else value
            print(f"  {key}={masked_value}")
    else:
        print("✅ Все переменные уже настроены")

def install_requirements():
    """Устанавливает необходимые пакеты"""
    requirements = [
        'python-telegram-bot==20.3',
        'requests',
        'pathlib',
    ]
    
    print("📦 Установка зависимостей...")
    
    for package in requirements:
        print(f"Installing {package}...")
        os.system(f"pip3 install {package}")
    
    print("✅ Зависимости установлены")

def create_gist_clone_dir():
    """Создает директорию для клона Gist"""
    gist_dir = Path("gist-baza")
    
    if gist_dir.exists():
        print("✅ Директория gist-baza уже существует")
        return
    
    print("📁 Создание директории для Gist...")
    
    # Читаем GIST_ID из .env
    env_path = Path(".env")
    gist_id = None
    
    if env_path.exists():
        for line in env_path.read_text().split('\n'):
            if line.startswith("GIST_ID="):
                gist_id = line.split('=', 1)[1].strip()
                break
    
    if gist_id:
        gist_url = f"https://gist.github.com/{gist_id}.git"
        print(f"🔗 Клонирование Gist: {gist_url}")
        
        result = os.system(f"git clone {gist_url} gist-baza")
        if result == 0:
            print("✅ Gist успешно клонирован в gist-baza/")
        else:
            print("❌ Ошибка клонирования Gist")
    else:
        print("⚠️ GIST_ID не найден в .env файле")
        gist_dir.mkdir()
        print("📁 Создана пустая директория gist-baza/")

def test_bot_config():
    """Тестирует конфигурацию бота"""
    env_path = Path(".env")
    
    if not env_path.exists():
        print("❌ Файл .env не найден")
        return False
    
    required_vars = ['TELEGRAM_BOT_TOKEN', 'AUTHORIZED_USER_IDS']
    missing_vars = []
    
    env_content = env_path.read_text()
    
    for var in required_vars:
        if f"{var}=" not in env_content:
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Отсутствуют переменные: {', '.join(missing_vars)}")
        return False
    
    print("✅ Конфигурация бота корректна")
    return True

def main():
    print("🚀 Настройка Smart Telegram Bot для FPF Baza")
    print("=" * 50)
    
    # Шаг 1: Установка зависимостей
    install_requirements()
    
    # Шаг 2: Настройка переменных окружения
    create_env_template()
    
    # Шаг 3: Настройка Gist директории
    create_gist_clone_dir()
    
    # Шаг 4: Тестирование конфигурации
    if test_bot_config():
        print("\n🎉 Настройка завершена!")
        print("\n📋 Следующие шаги:")
        print("1. Запустите бота: python3 smart_telegram_bot.py")
        print("2. Напишите боту /start в Telegram")
        print("3. Проверьте авторизацию")
        
        print("\n💡 JSON команды для Claude iPhone:")
        print('{"action": "read_sections", "limit": 5}')
        print('{"action": "update_section", "section": "секция", "changes": "новый текст"}')
        print('{"action": "add_section", "title": "Новая секция", "content": "содержимое"}')
        
    else:
        print("❌ Ошибки в конфигурации. Повторите настройку.")

if __name__ == "__main__":
    main()
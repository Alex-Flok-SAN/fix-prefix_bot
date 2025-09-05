#!/usr/bin/env python3
"""
Простая версия Telegram бота для Jupyter среды
"""

import os
import sys
from pathlib import Path

# Загружаем переменные из .env
env_path = Path(".env")
if env_path.exists():
    for line in env_path.read_text().split('\n'):
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            os.environ[key] = value

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_USER_ID = int(os.getenv("AUTHORIZED_USER_IDS", "0"))

if not BOT_TOKEN or not AUTHORIZED_USER_ID:
    print("❌ Переменные окружения не настроены!")
    sys.exit(1)

print(f"🤖 Запуск бота с токеном: {BOT_TOKEN[:20]}...")
print(f"👤 Авторизованный пользователь: {AUTHORIZED_USER_ID}")

# Простая проверка токена
import requests

# Проверяем токен
url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
response = requests.get(url)

if response.status_code == 200:
    bot_info = response.json()
    print(f"✅ Бот подключен: @{bot_info['result']['username']}")
    print(f"📛 Имя бота: {bot_info['result']['first_name']}")
    print("")
    print("🎯 БОТ ГОТОВ К РАБОТЕ!")
    print("=" * 40)
    print("📱 Откройте Telegram и найдите вашего бота")
    print("💬 Отправьте боту /start")
    print("📋 Попробуйте JSON команду:")
    print('{"action": "read_sections", "limit": 3}')
    print("")
    print("⚠️  ВНИМАНИЕ: Бот работает только в этой консоли")
    print("🔄 Для постоянной работы запустите в отдельном терминале")
else:
    print(f"❌ Ошибка токена: {response.status_code}")
    print(response.text)
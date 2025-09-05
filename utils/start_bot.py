#!/usr/bin/env python3
"""
Простой запуск Telegram бота
"""
import os
from pathlib import Path

# Загружаем переменные из .env
env_path = Path(".env")
if env_path.exists():
    for line in env_path.read_text().split('\n'):
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            os.environ[key] = value

# Импортируем и запускаем бота
from smart_telegram_bot import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
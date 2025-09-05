#!/bin/bash

export TELEGRAM_BOT_TOKEN=8473198397:AAHoOiO3s8lf3ds2yE4GhQvaVfFjdNwrGI4
export AUTHORIZED_USER_IDS=357809819

echo "🤖 Запуск исправленной версии Telegram бота..."
echo "📱 Найдите @fixprefix_bot в Telegram"
echo "🔧 Используется nest_asyncio для совместимости"

python3 sync/telegram/telegram_bot_fixed.py
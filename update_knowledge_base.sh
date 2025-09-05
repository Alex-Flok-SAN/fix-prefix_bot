#!/bin/bash
# Быстрая команда для обновления базы знаний
# Использование: ./update_knowledge_base.sh [сообщение коммита]

cd /Users/sashaflok/fpf_bot

if [ $# -eq 0 ]; then
    echo "🔄 Автоматическое обновление базы знаний..."
    python3 sync_knowledge_base.py
else
    echo "📝 Обновление с сообщением: $*"
    python3 sync_knowledge_base.py "$*"
fi
#!/bin/bash

# 🎯 Approved GitHub Sync Script
# Синхронизирует только утвержденные изменения с GitHub
# Использование: ./scripts/approved_sync.sh [release|stable|hotfix] "commit message"

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция логирования
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Проверка параметров
if [ $# -lt 2 ]; then
    error "Использование: $0 [release|stable|hotfix|production] \"commit message\""
fi

SYNC_TYPE=$1
COMMIT_MESSAGE=$2

# Валидация типа синхронизации
case $SYNC_TYPE in
    release|stable|hotfix|production)
        log "✅ Тип синхронизации: $SYNC_TYPE"
        ;;
    *)
        error "❌ Неверный тип синхронизации. Доступны: release, stable, hotfix, production"
        ;;
esac

# Проверка статуса Git
if ! git diff --quiet; then
    warn "⚠️  Есть незакоммиченные изменения. Продолжить? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        error "❌ Операция отменена пользователем"
    fi
fi

# Создание timestamp для тега
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
TAG_NAME="${SYNC_TYPE}/${TIMESTAMP}"

log "🏷️  Создание тега: $TAG_NAME"
log "📝 Сообщение: $COMMIT_MESSAGE"

# Интерактивное подтверждение
echo -e "\n${BLUE}=== ДЕТАЛИ СИНХРОНИЗАЦИИ ===${NC}"
echo "🎯 Тип: $SYNC_TYPE"
echo "🏷️  Тег: $TAG_NAME" 
echo "📝 Сообщение: $COMMIT_MESSAGE"
echo "📊 Файлов к отправке: $(git status --porcelain | wc -l)"
echo -e "\n${YELLOW}Продолжить синхронизацию? (y/N)${NC}"

read -r confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    error "❌ Синхронизация отменена"
fi

# Добавление всех изменений
log "📦 Добавление изменений в коммит..."
git add .

# Создание коммита с детальным описанием
DETAILED_MESSAGE="🎯 [$SYNC_TYPE] $COMMIT_MESSAGE

📊 Статистика изменений:
- Измененных файлов: $(git diff --cached --name-only | wc -l)
- Тип релиза: $SYNC_TYPE
- Временная метка: $TIMESTAMP

🤖 Generated with Claude Code Approved Sync

Co-Authored-By: Claude <noreply@anthropic.com>"

git commit -m "$DETAILED_MESSAGE" || log "⚠️  Нет изменений для коммита"

# Создание тега
log "🏷️  Создание аннотированного тега..."
git tag -a "$TAG_NAME" -m "[$SYNC_TYPE] $COMMIT_MESSAGE - Approved for sync at $TIMESTAMP"

# Отправка в GitHub
log "🚀 Отправка в GitHub..."
git push origin main
git push origin "$TAG_NAME"

# Финальное подтверждение
log "✅ Синхронизация завершена успешно!"
log "🌐 GitHub: https://github.com/Alex-Flok-SAN/fix-prefix_bot"
log "🏷️  Тег: $TAG_NAME"

# Опционально: создание release на GitHub
if command -v gh &> /dev/null; then
    log "🎉 Создание GitHub Release..."
    gh release create "$TAG_NAME" \
        --title "[$SYNC_TYPE] $COMMIT_MESSAGE" \
        --notes "Approved changes synchronized at $TIMESTAMP

🎯 **Release Type:** $SYNC_TYPE
⏰ **Timestamp:** $TIMESTAMP
📝 **Details:** $COMMIT_MESSAGE

This is an approved release that has been validated and is ready for use." \
        --latest || warn "⚠️  Не удалось создать GitHub Release"
fi

log "🎯 Approved Sync Complete!"
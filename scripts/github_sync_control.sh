#!/bin/bash

# 🔄 GitHub Sync Daemon Control Script

DAEMON_PID_FILE=".github_sync_daemon.pid"
DAEMON_SCRIPT="scripts/github_sync_daemon.py"

case "$1" in
    start)
        if [ -f "$DAEMON_PID_FILE" ]; then
            PID=$(cat $DAEMON_PID_FILE)
            if ps -p $PID > /dev/null 2>&1; then
                echo "🟡 Демон уже запущен (PID: $PID)"
                exit 1
            else
                rm -f $DAEMON_PID_FILE
            fi
        fi
        
        echo "🚀 Запуск GitHub Sync Daemon..."
        nohup python3 $DAEMON_SCRIPT > logs/github_sync_daemon.out 2>&1 &
        echo $! > $DAEMON_PID_FILE
        echo "✅ Демон запущен (PID: $!)"
        ;;
        
    stop)
        if [ -f "$DAEMON_PID_FILE" ]; then
            PID=$(cat $DAEMON_PID_FILE)
            if ps -p $PID > /dev/null 2>&1; then
                kill $PID
                rm -f $DAEMON_PID_FILE
                echo "🛑 Демон остановлен"
            else
                rm -f $DAEMON_PID_FILE
                echo "⚠️  Демон не был запущен"
            fi
        else
            echo "❌ PID файл не найден"
        fi
        ;;
        
    status)
        if [ -f "$DAEMON_PID_FILE" ]; then
            PID=$(cat $DAEMON_PID_FILE)
            if ps -p $PID > /dev/null 2>&1; then
                echo "🟢 Демон запущен (PID: $PID)"
            else
                echo "🔴 Демон не отвечает (PID файл найден, но процесс не найден)"
                rm -f $DAEMON_PID_FILE
            fi
        else
            echo "🔴 Демон не запущен"
        fi
        ;;
        
    sync)
        echo "🔄 Принудительная синхронизация..."
        python3 $DAEMON_SCRIPT --once
        ;;
        
    *)
        echo "Использование: $0 {start|stop|status|sync}"
        echo ""
        echo "Команды:"
        echo "  start  - Запустить демон синхронизации"
        echo "  stop   - Остановить демон"  
        echo "  status - Проверить статус демона"
        echo "  sync   - Принудительная разовая синхронизация"
        exit 1
        ;;
esac

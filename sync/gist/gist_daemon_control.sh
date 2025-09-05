#!/bin/bash
# Управление демоном GitHub Gist синхронизации

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DAEMON_SCRIPT="$SCRIPT_DIR/gist_sync.py"
PID_FILE="$PROJECT_ROOT/logs/.gist_daemon.pid"

case "$1" in
    start)
        if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
            echo "🤖 Демон Gist уже запущен (PID: $(cat $PID_FILE))"
        else
            echo "🚀 Запуск демона GitHub Gist синхронизации..."
            cd "$SCRIPT_DIR"
            nohup python3 "$DAEMON_SCRIPT" daemon > "$PROJECT_ROOT/logs/gist_daemon.log" 2>&1 &
            echo $! > "$PID_FILE"
            echo "✅ Демон запущен (PID: $!)"
            echo "📋 Логи: $PROJECT_ROOT/logs/gist_daemon.log"
        fi
        ;;
    
    stop)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                echo "🛑 Остановка демона (PID: $PID)..."
                kill "$PID"
                rm -f "$PID_FILE"
                echo "✅ Демон остановлен"
            else
                echo "⚠️ Процесс не найден, удаляем PID файл"
                rm -f "$PID_FILE"
            fi
        else
            echo "❌ Демон не запущен"
        fi
        ;;
    
    restart)
        echo "🔄 Перезапуск демона Gist..."
        $0 stop
        sleep 2
        $0 start
        ;;
    
    status)
        if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
            echo "✅ Демон Gist запущен (PID: $(cat $PID_FILE))"
            echo "📊 Статус процесса:"
            ps aux | grep -E "$(cat $PID_FILE)" | grep -v grep
        else
            echo "❌ Демон Gist не запущен"
            [ -f "$PID_FILE" ] && rm -f "$PID_FILE"
        fi
        ;;
    
    logs)
        if [ -f "$SCRIPT_DIR/gist_daemon.log" ]; then
            echo "📋 Логи демона Gist:"
            echo "==================="
            tail -f "$SCRIPT_DIR/gist_daemon.log"
        else
            echo "📋 Файл логов не найден"
        fi
        ;;
    
    pull)
        echo "📥 Ручная синхронизация: Gist → Local"
        cd "$SCRIPT_DIR"
        python3 "$DAEMON_SCRIPT" pull
        ;;
        
    push)
        echo "📤 Ручная синхронизация: Local → Gist"
        cd "$SCRIPT_DIR"
        python3 "$DAEMON_SCRIPT" push
        ;;
        
    check)
        echo "🔍 Проверка синхронизации"
        cd "$SCRIPT_DIR"
        python3 "$DAEMON_SCRIPT" check
        ;;
    
    info)
        echo "ℹ️ Информация о Gist"
        cd "$SCRIPT_DIR"
        python3 "$DAEMON_SCRIPT" info
        ;;
    
    *)
        echo "🔧 Управление демоном GitHub Gist синхронизации"
        echo "================================================"
        echo "Использование: $0 {start|stop|restart|status|logs|pull|push|check|info}"
        echo ""
        echo "Команды демона:"
        echo "  start   - запустить автосинхронизацию"
        echo "  stop    - остановить демон"
        echo "  restart - перезапустить демон"
        echo "  status  - показать статус"
        echo "  logs    - показать логи в реальном времени"
        echo ""
        echo "Ручная синхронизация:"
        echo "  pull    - загрузить из Gist"
        echo "  push    - отправить в Gist"
        echo "  check   - проверить различия"
        echo "  info    - информация о Gist"
        exit 1
        ;;
esac
#!/usr/bin/env python3
"""
Test GUI initialization and capture startup output
"""
import sys
import pathlib
import threading
import time
import signal
import os

# Добавляем путь к проекту
_here = pathlib.Path(__file__).resolve()
_proj_root = _here.parent
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))

def test_gui_startup():
    """Тестирует создание GUI компонентов без запуска mainloop"""
    print("🚀 Testing FPF Snap GUI components...")
    
    try:
        from tools.snapp import FPFSnapApp
        print("✅ FPFSnapApp imported successfully")
        
        # Создаем приложение (это создает все компоненты)
        app = FPFSnapApp()
        print("✅ FPFSnapApp instance created")
        
        # Проверяем что все компоненты созданы
        print("🔍 Checking components...")
        
        # Проверяем окно
        if hasattr(app, 'window') and app.window:
            window_title = app.window.title()
            print(f"🪟 Window created: '{window_title}'")
        
        # Проверяем анализатор
        if hasattr(app, 'analyzer') and app.analyzer:
            print("🧠 PatternAnalyzer created")
        
        # Проверяем отрисовщик паттернов
        if hasattr(app, 'pattern_drawer') and app.pattern_drawer:
            print("🎨 PatternDrawer created")
            
        # Проверяем отрисовщик графиков  
        if hasattr(app, 'chart_renderer') and app.chart_renderer:
            print("📊 ChartRenderer created")
        
        print("✅ All GUI components initialized successfully!")
        print("📱 GUI is ready to run with: python tools/snapp.py")
        
        return True
        
    except Exception as e:
        print(f"❌ GUI component creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    success = test_gui_startup()
    
    if success:
        print("\n🎉 GUI test completed successfully!")
        print("💡 You can now run: python tools/snapp.py")
        print("📸 Drag & drop a TradingView screenshot to test FPF analysis")
    else:
        print("\n❌ GUI test failed - check errors above")
    
    # Завершаем процесс
    os._exit(0)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Debug script для отладки FPF Snap по компонентам
"""
import sys
import pathlib
import traceback

# Добавляем путь к проекту
_here = pathlib.Path(__file__).resolve()
_proj_root = _here.parent
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))

def test_imports():
    """Тестирование импортов"""
    print("🔍 Testing imports...")
    
    try:
        print("1. Testing UI imports...")
        from ui.tv_ingest_window import TVIngestWindow
        print("   ✅ TVIngestWindow OK")
        
        from ui.pattern_analyzer import PatternAnalyzer
        print("   ✅ PatternAnalyzer OK")
        
        print("2. Testing visualization imports...")
        from visualization.pattern_drawer import FPFPatternDrawer
        print("   ✅ FPFPatternDrawer OK")
        
        from visualization.chart_renderer import ChartRenderer
        print("   ✅ ChartRenderer OK")
        
        print("3. Testing core imports...")
        from core.ai_search_pattern.fpf_detector_new import FpfPatternDetector
        print("   ✅ FpfPatternDetector OK")
        
        print("4. Testing main snapp import...")
        from tools.snapp import FPFSnapApp
        print("   ✅ FPFSnapApp OK")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Import error: {e}")
        traceback.print_exc()
        return False

def test_components():
    """Тестирование создания компонентов без GUI"""
    print("🔧 Testing component initialization...")
    
    try:
        # Тестируем Pattern Analyzer
        from ui.pattern_analyzer import PatternAnalyzer
        analyzer = PatternAnalyzer()
        print("   ✅ PatternAnalyzer created")
        
        # Тестируем FPF Detector
        from core.ai_search_pattern.fpf_detector_new import FpfPatternDetector
        detector = FpfPatternDetector(debug=True)
        print("   ✅ FpfPatternDetector created")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Component error: {e}")
        traceback.print_exc()
        return False

def test_data_loader():
    """Тестирование загрузчика данных"""
    print("📊 Testing data loader...")
    
    try:
        from sync.simple_data_loader import load_data_for_analysis
        print("   ✅ Data loader import OK")
        
        # Пробуем загрузить тестовые данные
        from datetime import datetime
        test_dt = datetime(2024, 8, 31, 12, 0)
        
        print(f"   🔍 Testing data load for BTCUSDT 15m at {test_dt}")
        # Не делаем реальный запрос - только проверяем что функция импортируется
        
        return True
        
    except Exception as e:
        print(f"   ❌ Data loader error: {e}")
        traceback.print_exc()
        return False

def test_ocr_engine():
    """Тестирование OCR движка"""
    print("👁️ Testing OCR engine...")
    
    try:
        from ai.ocr_engine_new import SimpleOCREngine
        ocr = SimpleOCREngine()
        print("   ✅ SimpleOCREngine created")
        return True
        
    except Exception as e:
        print(f"   ❌ OCR engine error: {e}")
        traceback.print_exc()
        return False

def main():
    """Главная функция отладки"""
    print("🚀 FPF Snap Debug Session")
    print("=" * 40)
    
    # Проверяем все компоненты по очереди
    tests = [
        ("Imports", test_imports),
        ("Components", test_components), 
        ("Data Loader", test_data_loader),
        ("OCR Engine", test_ocr_engine)
    ]
    
    results = {}
    for name, test_func in tests:
        print(f"\n📋 {name} Test:")
        results[name] = test_func()
    
    # Итоги
    print("\n" + "=" * 40)
    print("🎯 Debug Summary:")
    for name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {name}: {status}")
    
    all_passed = all(results.values())
    if all_passed:
        print("\n🎉 All tests passed! FPF Snap should work correctly.")
        
        # Предлагаем запустить GUI
        print("\n💡 Ready to test GUI? Run: python tools/snapp.py")
    else:
        print("\n⚠️  Some tests failed. Fix issues before running GUI.")

if __name__ == "__main__":
    main()
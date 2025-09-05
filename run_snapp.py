#!/usr/bin/env python3
"""
Wrapper for running FPF Snap with error handling
"""
import sys
import pathlib
import traceback

# Добавляем путь к проекту
_here = pathlib.Path(__file__).resolve()
_proj_root = _here.parent
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))

def main():
    print("🚀 Starting FPF Snap with error handling...")
    
    try:
        from tools.snapp import FPFSnapApp
        print("✅ Import successful")
        
        app = FPFSnapApp() 
        print("✅ App created, starting GUI...")
        
        app.run()
        
    except KeyboardInterrupt:
        print("🛑 User interrupted")
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()
    finally:
        print("👋 FPF Snap session ended")

if __name__ == "__main__":
    main()
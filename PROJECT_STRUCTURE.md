# FPF Bot Project Structure

## 📁 Organized Directory Layout

```
fpf_bot/
├── 📂 core/                 # Core business logic
│   ├── event_bus.py        # Event system
│   ├── signal_manager.py   # Signal management
│   ├── fix_prefix_detector.py # FPF pattern detection
│   ├── data_fetcher.py     # Data fetching logic
│   └── ...
│
├── 📂 ui/                   # User interface
│   ├── main_window.py      # Main GUI window
│   ├── signals_panel.py    # Signals display panel
│   └── filters_panel.py    # Filters panel
│
├── 📂 ai/                   # AI/ML components
│   ├── ocr_engine.py       # OCR for TradingView
│   └── ai_search_pattern.py # Pattern search AI
│
├── 📂 tools/                # Standalone tools
│   ├── tv_ingest_app.py   # TradingView screenshot tool
│   └── ...
│
├── 📂 scripts/              # Utility scripts
│   ├── run_stream.py       # Stream runner
│   └── ...
│
├── 📂 sync/                 # Synchronization tools
│   ├── 📂 telegram/        # Telegram bot files
│   │   ├── telegram_bot_fixed.py
│   │   └── ...
│   ├── 📂 gist/           # GitHub Gist sync
│   │   ├── gist_sync.py
│   │   └── gist_daemon_control.sh
│   └── 📂 github/         # GitHub integration
│
├── 📂 utils/                # Utility functions
│   ├── binance_m1_export.py
│   ├── fetch_binance_klines.py
│   └── ...
│
├── 📂 data/                 # Data storage
│   ├── history/
│   ├── signals.db
│   └── ...
│
├── 📂 data_1m/             # Minute data
├── 📂 config/              # Configuration
│   ├── pairs_usdt.txt
│   └── settings.yaml
│
├── 📂 logs/                # All log files
│   ├── gist_daemon.log
│   └── ...
│
├── 📂 docs/                # Documentation
│   ├── idea_answers.txt
│   └── baza1.txt
│
├── 📄 baza.txt             # Main knowledge base
├── 📄 run_fpf_bot.py       # Main launcher
├── 📄 run_bot.sh           # Telegram bot launcher
├── 📄 gist_control.sh      # Symlink to sync/gist/gist_daemon_control.sh
└── 📄 requirements.txt     # Python dependencies
```

## 🔧 Quick Commands

### Start FPF Bot GUI:
```bash
python3 run_fpf_bot.py
```

### Start Telegram Bot:
```bash
./run_bot.sh
```

### Control Gist Sync:
```bash
./gist_control.sh start|stop|status|restart
```

## 📝 Notes

- All synchronization tools moved to `sync/` folder
- Utility scripts moved to `utils/` folder  
- Logs centralized in `logs/` folder
- Documentation in `docs/` folder
- Main knowledge base `baza.txt` remains in root for easy access
- Symlinks created for frequently used commands
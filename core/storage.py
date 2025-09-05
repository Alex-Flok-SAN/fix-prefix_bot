import sqlite3
from pathlib import Path
from typing import Dict, Any

class Storage:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute(
            '''CREATE TABLE IF NOT EXISTS signals (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               ts INTEGER,
               symbol TEXT,
               tf TEXT,
               direction TEXT,
               fix_high REAL,
               fix_low REAL,
               break_ts INTEGER,
               break_price REAL,
               vol_fix REAL,
               ai_score REAL,
               note TEXT
            )'''
        )
        cur.execute('CREATE INDEX IF NOT EXISTS idx_signals_time ON signals(ts)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_signals_sym_tf ON signals(symbol, tf)')
        con.commit()
        con.close()

    def insert_signal(self, row: Dict[str, Any]) -> None:
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute('''INSERT INTO signals
            (ts, symbol, tf, direction, fix_high, fix_low, break_ts, break_price, vol_fix, ai_score, note)
            VALUES (:ts,:symbol,:tf,:direction,:fix_high,:fix_low,:break_ts,:break_price,:vol_fix,:ai_score,:note)''', row)
        con.commit()
        con.close()

    def fetch_last(self, limit: int = 50):
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute('SELECT ts, symbol, tf, direction, break_price FROM signals ORDER BY ts DESC LIMIT ?', (limit,))
        rows = cur.fetchall()
        con.close()
        return rows

    def fetch_signal(self, symbol: str, tf: str, break_ts: int):
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute(
            '''SELECT * FROM signals WHERE symbol = ? AND tf = ? AND break_ts = ? LIMIT 1''',
            (symbol, tf, break_ts)
        )
        row = cur.fetchone()
        con.close()
        return row
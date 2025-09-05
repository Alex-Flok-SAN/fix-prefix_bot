from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel
)
from typing import Any, Dict
from datetime import datetime
import webbrowser

# ZoneInfo (Python 3.9+); fallback to None if unavailable
try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


class SignalsPanel(QWidget):
    """Панель отображения сигналов Fix‑Prefix.

    Поддерживает приём данных как словарём, так и позиционными аргументами.
    Ожидаемые ключи: symbol, tf, direction, break_price, ai_score, tv_url,
    fix_high_url|tv_fix_high, fix_low_url|tv_fix_low, return_url|tv_return, ts.
    """

    def __init__(self) -> None:
        super().__init__()

        self._tz_name = "Europe/Moscow"
        self._tz = ZoneInfo(self._tz_name) if ZoneInfo else None

        root = QVBoxLayout(self)

        title = QLabel("Сигналы Fix‑Prefix")
        title.setStyleSheet("font-weight:600; margin:4px 0 6px 0;")
        root.addWidget(title)

        # Таблица: Время, Пара, TF, Направление, Цена пробоя, AI, TV, FIX H, FIX L, RETURN
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "Время", "Пара", "TF", "Направление", "Цена пробоя", "AI", "TV", "FIX H", "FIX L", "RETURN"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for col in (6, 7, 8, 9):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        root.addWidget(self.table)

    # ===== Публичное API =====
    def set_timezone(self, tz_name: str) -> None:
        self._tz_name = tz_name or "Europe/Moscow"
        try:
            self._tz = ZoneInfo(self._tz_name) if ZoneInfo else None
        except Exception:
            self._tz = None

    def clear(self) -> None:
        self.table.setRowCount(0)

    def add_signal(self, *args: Any, **kwargs: Any) -> None:
        """Добавить сигнал.

        Поддерживает формы вызова:
          add_signal(dict_row)
          add_signal(symbol, tf, direction, price, ai_score, url[, ts])
          add_signal(**row)
        """
        print("[SignalsPanel] add_signal called with:", args if args else kwargs)
        row: Dict[str, Any]
        if len(args) == 1 and isinstance(args[0], dict) and not kwargs:
            row = dict(args[0])
        elif kwargs:
            row = dict(kwargs)
        else:
            # позиционные аргументы: symbol, tf, direction, price, ai_score, url, ts
            keys = ["symbol", "tf", "direction", "break_price", "ai_score", "tv_url", "ts"]
            row = {k: (args[i] if i < len(args) else None) for i, k in enumerate(keys)}

        try:
            self._add_signal_row(dict(row))
        except Exception as e:
            import traceback
            print(f"[SignalsPanel] add_signal error: {e}")
            traceback.print_exc()

    # ===== Внутреннее =====
    def _fmt_time(self, v: Any) -> str:
        if v is None or v == "":
            return ""
        try:
            iv = int(v)
        except Exception:
            return str(v)
        # мс → сек при больших значениях
        if iv > 10_000_000_000:
            ts = iv / 1000.0
        else:
            ts = iv
        try:
            if self._tz is not None:
                dt = datetime.fromtimestamp(ts, self._tz)
            else:
                dt = datetime.fromtimestamp(ts)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(v)

    def _open_tv(self, url: str) -> None:
        if url:
            try:
                webbrowser.open(url)
            except Exception:
                pass

    def _add_signal_row(self, row: Dict[str, Any]) -> None:
        print("[SignalsPanel] _add_signal_row keys:", list(row.keys()))
        time_str = self._fmt_time(row.get("ts"))
        symbol = str(row.get("symbol", ""))
        tf = str(row.get("tf", ""))
        direction = str(row.get("direction", ""))
        price = row.get("break_price")
        if price is None:
            price = row.get("price", "")
        price_str = f"{price}" if price is not None else ""
        ai_val = row.get("ai_score", row.get("ai", ""))
        ai = "" if ai_val is None else str(ai_val)
        tv_url = str(row.get("tv_url") or "")
        tv_fix_h = str(row.get("fix_high_url") or row.get("tv_fix_high") or "")
        tv_fix_l = str(row.get("fix_low_url") or row.get("tv_fix_low") or "")
        tv_return = str(row.get("return_url") or row.get("tv_return") or "")

        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(time_str))
        self.table.setItem(r, 1, QTableWidgetItem(symbol))
        self.table.setItem(r, 2, QTableWidgetItem(tf))
        self.table.setItem(r, 3, QTableWidgetItem(direction))
        self.table.setItem(r, 4, QTableWidgetItem(price_str))
        self.table.setItem(r, 5, QTableWidgetItem(ai))

        def make_btn(u: str, tip: str) -> QPushButton:
            btn = QPushButton("Открыть")
            btn.setToolTip(tip)
            btn.setEnabled(bool(u))
            if u:
                btn.clicked.connect(lambda _, url=u: self._open_tv(url))
            return btn

        self.table.setCellWidget(r, 6, make_btn(tv_url, "Открыть TradingView на свече пробоя"))
        self.table.setCellWidget(r, 7, make_btn(tv_fix_h, "Открыть точку FIX HIGH"))
        self.table.setCellWidget(r, 8, make_btn(tv_fix_l, "Открыть точку FIX LOW"))
        self.table.setCellWidget(r, 9, make_btn(tv_return, "Открыть свечу возврата"))

        self.table.scrollToBottom()
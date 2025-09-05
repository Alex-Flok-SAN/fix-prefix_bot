from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QCheckBox, QListWidget, QListWidgetItem
from PyQt5.QtWidgets import QAbstractItemView
from PyQt5.QtCore import Qt, pyqtSignal

from typing import Dict, Any
from PyQt5.QtGui import QBrush, QColor

class FiltersPanel(QWidget):
    """Левая панель фильтров без кнопок Start/Stop.
    Содержит: таймфреймы, список пар, кнопку DEMO, локальный индикатор статуса,
    а также утилиты подсветки активной пары.
    """
    demo_clicked = pyqtSignal()
    signal_generated = pyqtSignal(dict)
    def __init__(self, pairs, parent=None):
        super().__init__(parent)
        # --- таймфреймы ---
        self.cb_5m = QCheckBox("M5");  self.cb_5m.setChecked(True)
        self.cb_15m = QCheckBox("M15"); self.cb_15m.setChecked(True)
        self.cb_30m = QCheckBox("M30"); self.cb_30m.setChecked(True)
        self.cb_1h = QCheckBox("H1");   self.cb_1h.setChecked(True)

        # --- список пар ---
        self.pairs_list = QListWidget()
        self.pairs_list.setSelectionMode(QAbstractItemView.MultiSelection)
        for p in pairs:
            self.pairs_list.addItem(p)
        if self.pairs_list.count():
            self.pairs_list.setCurrentRow(0)

        # --- кнопка DEMO (для проверки пайплайна сигналов) ---
        self.demo_btn = QPushButton("Добавить DEMO сигнал")
        self.demo_btn.clicked.connect(self.demo_clicked.emit)

        # --- локальный статус подключения (синхронизируется с нижним) ---
        self.status_lbl = QLabel("Offline")
        self.status_lbl.setStyleSheet("color: #d66; font-weight: 600;")

        # --- компоновка ---
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Таймфреймы"))
        layout.addWidget(self.cb_5m)
        layout.addWidget(self.cb_15m)
        layout.addWidget(self.cb_30m)
        layout.addWidget(self.cb_1h)
        layout.addSpacing(8)
        layout.addWidget(QLabel("Пары (до 50)"))
        layout.addWidget(self.pairs_list)
        layout.addSpacing(8)
        layout.addWidget(self.demo_btn)
        layout.addSpacing(12)
        layout.addWidget(QLabel("Статус подключения"))
        layout.addWidget(self.status_lbl)
        layout.addStretch()

        self._active_item = None  # type: QListWidgetItem | None

    # ---- API ----
    def selected_timeframes(self):
        tfs = []
        if self.cb_5m.isChecked():  tfs.append("5m")
        if self.cb_15m.isChecked(): tfs.append("15m")
        if self.cb_30m.isChecked(): tfs.append("30m")
        if self.cb_1h.isChecked():  tfs.append("1h")
        return tfs

    def selected_pair(self):
        item = self.pairs_list.currentItem()
        return item.text() if item else None

    def selected_pairs(self):
        """Вернёт список выбранных пар (до 50). Если ничего не выбрано — вернёт все (до 50)."""
        items = self.pairs_list.selectedItems()
        if items:
            return sorted([it.text() for it in items])[:50]
        # если ничего не выбрано — берём все, но не более 50
        return sorted([self.pairs_list.item(i).text() for i in range(min(self.pairs_list.count(), 50))])

    def emit_signal(self, payload: Dict[str, Any]):
        """Удобный способ отправить сигнал о найденном паттерне в UI.
        Ожидается словарь формата как у реального сигнала: {
            'symbol': str, 'tf': str, 'direction': 'long'|'short',
            'break_price': float, 'ts': int, 'ai_score': Optional[float], 'tv_url': str, ...
        }
        """
        try:
            self.signal_generated.emit(dict(payload))
        except Exception:
            pass

    def set_status(self, text: str, ok: bool):
        self.status_lbl.setText(text)
        self.status_lbl.setStyleSheet(
            "color: #4caf50; font-weight: 600;" if ok else "color: #d66; font-weight: 600;"
        )
        print(f"[FiltersPanel] Status changed to '{text}', ok={ok}")

    def set_active_pair(self, symbol: str):
        items = self.pairs_list.findItems(symbol, Qt.MatchExactly)
        if not items:
            return
        it = items[0]
        row = self.pairs_list.row(it)
        # блокируем сигналы на время программной перестановки/выделения
        self.pairs_list.blockSignals(True)
        self.pairs_list.takeItem(row)
        self.pairs_list.insertItem(0, it)
        self.pairs_list.setCurrentItem(it)
        self.pairs_list.blockSignals(False)
        # подсветка
        if self._active_item and self._active_item is not it:
            self._active_item.setBackground(QBrush())
            self._active_item.setForeground(QBrush())
        it.setBackground(QBrush(QColor("#334155")))
        it.setForeground(QBrush(QColor("#e5e7eb")))
        self._active_item = it

    def clear_active_pair_highlight(self):
        if self._active_item:
            self._active_item.setBackground(QBrush())
            self._active_item.setForeground(QBrush())
            self._active_item = None
        self.set_status("Offline", ok=False)
import json, time
from pathlib import Path
from typing import Dict, Any, Optional
from .storage import Storage
from .event_bus import EventBus

class SignalManager:
    TOPIC_SIGNAL = "signal.detected"

    def __init__(self, bus: EventBus, db_path: str, log_dir: str) -> None:
        self.bus = bus
        self.storage = Storage(db_path)
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.bus.subscribe(self.TOPIC_SIGNAL, self._on_signal)

    def _on_signal(self, sig: Dict[str, Any]) -> None:
        # ----- Normalize & enrich payload for UI -----
        direction = (sig.get("direction") or "").lower()
        ui_row: Dict[str, Any] = {
            "symbol": sig.get("symbol"),
            "tf": sig.get("tf"),
            "direction": sig.get("direction"),
            "fix_high": sig.get("fix_high"),
            "fix_low": sig.get("fix_low"),
            "fix_high_ts": sig.get("fix_high_ts"),
            "fix_low_ts": sig.get("fix_low_ts"),
            "return_ts": sig.get("return_ts"),
            "ts": sig.get("ts"),                 # event time (ms or s from detector)
            "break_ts": sig.get("break_ts"),      # final break time if present
            "break_price": sig.get("break_price"),
            "vol_fix": sig.get("vol_fix", 0.0),
            "ai_score": sig.get("ai_score", None),
            "note": sig.get("note", None),
            # pass through links for buttons
            "tv_url": sig.get("tv_url"),
            "fix_high_url": sig.get("fix_high_url") or sig.get("tv_fix_high"),
            "fix_low_url": sig.get("fix_low_url") or sig.get("tv_fix_low"),
            "return_url": sig.get("return_url") or sig.get("tv_return"),
        }
        # Normalize integer-like fields
        for k in ("ts", "break_ts", "fix_high_ts", "fix_low_ts", "return_ts"):
            if ui_row.get(k) is not None:
                try:
                    ui_row[k] = int(ui_row[k])
                except (ValueError, TypeError):
                    ui_row[k] = None

        # ----- Store only FINAL signals (not setups) -----
        is_setup = direction == "setup"
        if not is_setup:
            # Build DB row (keep original schema; use current insert time for ts)
            db_row = {
                "ts": int(time.time() * 1000),
                "symbol": ui_row.get("symbol"),
                "tf": ui_row.get("tf"),
                "direction": ui_row.get("direction"),
                "fix_high": ui_row.get("fix_high"),
                "fix_low": ui_row.get("fix_low"),
                "break_ts": ui_row.get("break_ts"),
                "break_price": ui_row.get("break_price"),
                "vol_fix": ui_row.get("vol_fix", 0.0),
                "ai_score": ui_row.get("ai_score"),
                "note": ui_row.get("note"),
            }
            # Normalize break_ts to int or None
            if db_row["break_ts"] is not None:
                try:
                    db_row["break_ts"] = int(db_row["break_ts"])
                except (ValueError, TypeError):
                    db_row["break_ts"] = None

            # prevent duplicates by symbol, tf, break_ts (only when break_ts present)
            if db_row["break_ts"] is not None:
                existing = self.storage.fetch_signal(db_row["symbol"], db_row["tf"], db_row["break_ts"])
                if existing:
                    # still fan out to UI/log for visibility, but skip DB insert
                    # append log line and fan-out below
                    pass
                else:
                    self.storage.insert_signal(db_row)

        # ----- Append log line (rich UI payload) -----
        try:
            log_path = self.log_dir / "signals.log"
            with log_path.open("a") as f:
                f.write(json.dumps(ui_row, ensure_ascii=False) + "\n")
        except Exception:
            pass

        # ----- Fan-out to UI -----
        self.bus.publish("ui.signal", ui_row)

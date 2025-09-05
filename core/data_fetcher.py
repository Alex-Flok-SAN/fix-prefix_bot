import threading
import time
import random
from typing import List, Dict, Tuple, Optional, Any
import requests

from .event_bus import EventBus

TF_SECONDS = {
    "5m": 5 * 60,
    "15m": 15 * 60,
    "30m": 30 * 60,
    "1h": 60 * 60,
}

FAPI_BASE = "https://fapi.binance.com"

class DataFetcher:
    """Простой REST-пуллинг USDT-M Futures без зависимостей от SDK.
    Берём fapi/v1/klines и публикуем *закрытую* свечу как 'candle.closed'.
    """
    def __init__(self, bus: EventBus, poll_overrides: Dict[str, int] = None, session: Optional[requests.Session] = None) -> None:
        self.bus = bus
        self._threads: List[threading.Thread] = []
        self._stop = threading.Event()
        self._last_closed_ts: Dict[Tuple[str,str], int] = {}
        self._poll_overrides = poll_overrides or {}
        self._session = session or requests.Session()
        self._session.headers.update({"User-Agent": "fpf-bot/0.1"})

    def start(self, symbols: List[str], tfs: List[str]) -> None:
        self._stop.clear()
        for s in symbols:
            for tf in tfs:
                if tf not in TF_SECONDS:
                    continue
                t = threading.Thread(target=self._poll_loop, args=(s, tf), daemon=True)
                t.start()
                self._threads.append(t)

    def stop(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=1.0)
        self._threads.clear()

    def _poll_loop(self, symbol: str, tf: str) -> None:
        interval_sec = self._poll_overrides.get(tf, 3)  # опрос каждые 3с
        key = (symbol, tf)
        # Создаём сессию отдельно для каждого потока
        sess = requests.Session()
        sess.headers.update({"User-Agent": "fpf-bot/0.1"})
        backoff_sec = 0
        try:
            while not self._stop.is_set():
                try:
                    url = f"{FAPI_BASE}/fapi/v1/klines"
                    params = {"symbol": symbol, "interval": tf, "limit": 3}
                    r = sess.get(url, params=params, timeout=10)
                    try:
                        r.raise_for_status()
                    except requests.HTTPError as he:
                        # Handle rate limits / bans gracefully
                        ra = r.headers.get("Retry-After") if r is not None else None
                        if r is not None and r.status_code in (418, 429):
                            try:
                                backoff_sec = max(backoff_sec, int(ra)) if ra else max(backoff_sec, 10)
                            except Exception:
                                backoff_sec = max(backoff_sec, 10)
                        elif r is not None and 500 <= r.status_code < 600:
                            backoff_sec = max(backoff_sec, 5)
                        raise

                    try:
                        klines = r.json()
                    except ValueError:
                        print(f"[DataFetcher] {symbol} {tf} JSON decode error")
                        # modest backoff on bad payload
                        backoff_sec = max(backoff_sec, 3)
                        klines = None

                    if not klines or len(klines) < 2:
                        # nothing to do; fall through to sleep
                        pass
                    else:
                        prev = klines[-2]  # ЗАКРЫТАЯ свеча
                        open_time_ms = int(prev[0])
                        close_time_ms = int(prev[6])
                        if self._last_closed_ts.get(key) != close_time_ms:
                            self._last_closed_ts[key] = close_time_ms
                            payload: Dict[str, Any] = {
                                "symbol": symbol,
                                "tf": tf,
                                "open_time": open_time_ms,
                                "open": float(prev[1]),
                                "high": float(prev[2]),
                                "low": float(prev[3]),
                                "close": float(prev[4]),
                                "volume": float(prev[5]),
                                "close_time": close_time_ms,
                                "ts": int(time.time() * 1000),
                            }
                            self.bus.publish("candle.closed", payload)

                    # success path resets backoff a bit (don't flap hard)
                    backoff_sec = 0 if backoff_sec <= 1 else backoff_sec - 1
                except Exception as e:
                    print(f"[DataFetcher] {symbol} {tf} error: {e}")
                    # Exponential-ish backoff, capped
                    backoff_sec = min(60, max(backoff_sec * 2, 5) or 5)
                # Sleep with jitter to avoid thundering herd
                sleep_sec = max(interval_sec, backoff_sec)
                sleep_sec += random.uniform(0, 0.3)
                time.sleep(sleep_sec)
        finally:
            try:
                sess.close()
            except Exception:
                pass

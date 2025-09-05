from __future__ import annotations
from collections import defaultdict
import threading
from typing import Callable, Any

class EventBus:
    _instance = None
    _init_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._subscribers = defaultdict(list)
                cls._instance._lock = threading.RLock()
        return cls._instance

    def subscribe(self, topic: str, handler: Callable[[Any], None]):
        with self._lock:
            self._subscribers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable[[Any], None]):
        with self._lock:
            if topic in self._subscribers and handler in self._subscribers[topic]:
                self._subscribers[topic].remove(handler)
                # Remove topic key if no subscribers remain
                if not self._subscribers[topic]:
                    del self._subscribers[topic]

    def subscriber_count(self, topic: str) -> int:
        """Return the number of subscribers for the given topic."""
        with self._lock:
            return len(self._subscribers.get(topic, []))

    def publish(self, topic: str, payload: Any):
        with self._lock:
            subs = list(self._subscribers.get(topic, []))
        for fn in subs:
            try:
                fn(payload)
            except Exception as e:
                print(f"[EventBus] handler error on topic '{topic}': {e}")

_bus_singleton: EventBus | None = None

def get_bus() -> EventBus:
    global _bus_singleton
    if _bus_singleton is None:
        _bus_singleton = EventBus()
    return _bus_singleton
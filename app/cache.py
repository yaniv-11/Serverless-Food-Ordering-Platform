"""In-process stand-in for Upstash Redis. Same role the Lambdas use Upstash
for - restaurant read-through caching and order idempotency claims - just
backed by a dict instead of a network call, since a local single-process
dev server has no need for an external cache. State does not survive a
restart; that's fine for local dev (an idempotency replay window resetting
on restart is a non-issue outside of production).
"""

import threading
import time
from typing import Optional


class TTLCache:
    def __init__(self):
        self._store = {}  # key -> (value, expires_at)
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at is not None and expires_at < time.time():
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        with self._lock:
            self._store[key] = (value, time.time() + ttl_seconds)

    def set_nx(self, key: str, value: str, ttl_seconds: int) -> bool:
        """Atomic claim, mirroring Upstash's SET NX EX. Returns True if this
        call claimed the key, False if it was already held (and not expired)."""
        with self._lock:
            entry = self._store.get(key)
            if entry is not None:
                existing_value, expires_at = entry
                if expires_at is None or expires_at >= time.time():
                    return False
            self._store[key] = (value, time.time() + ttl_seconds)
            return True

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)


restaurant_cache = TTLCache()
idempotency_cache = TTLCache()

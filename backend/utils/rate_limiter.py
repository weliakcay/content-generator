import time
from threading import Lock


class RateLimiter:
    """Simple rate limiter for scraping requests."""

    def __init__(self, min_interval: float = 3.0):
        self.min_interval = min_interval
        self._last_call = 0.0
        self._lock = Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.time()
            elapsed = now - self._last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_call = time.time()

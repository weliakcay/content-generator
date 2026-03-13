from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import Lock


class JsonStore:
    """Thread-safe JSON file read/write with atomic writes."""

    _locks: dict[str, Lock] = {}
    _global_lock = Lock()

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        key = str(self.file_path.resolve())
        with JsonStore._global_lock:
            if key not in JsonStore._locks:
                JsonStore._locks[key] = Lock()
            self._lock = JsonStore._locks[key]

    def read(self) -> dict:
        with self._lock:
            if not self.file_path.exists():
                return {}
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)

    def write(self, data: dict) -> None:
        with self._lock:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(
                dir=self.file_path.parent, suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, self.file_path)
            except Exception:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise

    def update(self, key: str, value) -> None:
        data = self.read()
        data[key] = value
        self.write(data)

    def append_to_list(self, key: str, item) -> None:
        data = self.read()
        if key not in data:
            data[key] = []
        data[key].append(item)
        self.write(data)

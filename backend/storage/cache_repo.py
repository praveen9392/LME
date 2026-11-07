"""
JSON cache repository for questionnaire answers and AI job scores.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class JsonCache:
    """Thread-safe and error-resilient JSON key-value store."""

    def __init__(self, file_path: Path | str) -> None:
        self.file_path = Path(file_path)

    def load(self) -> Dict[str, Any]:
        if not self.file_path.exists():
            return {}
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save(self, data: Dict[str, Any]) -> None:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self.load().get(key, default)

    def set(self, key: str, value: Any) -> None:
        data = self.load()
        data[key] = value
        self.save(data)

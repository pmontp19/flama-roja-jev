from __future__ import annotations

import json
from pathlib import Path


class JsonlTrace:
    def __init__(self, path: str | Path | None) -> None:
        self._file = open(path, "a", encoding="utf-8") if path else None

    def log(self, record: dict[str, object]) -> None:
        if self._file is None:
            return
        self._file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        self._file.flush()

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

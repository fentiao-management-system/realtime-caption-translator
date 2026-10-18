from __future__ import annotations

import datetime
import json
from pathlib import Path


class SessionRecorder:
    """把对话记录以 JSONL 格式写入 sessions 目录。"""

    def __init__(self, session_dir: Path) -> None:
        self.session_dir = Path(session_dir)
        self.path: Path | None = None
        self._file = None

    def start(self) -> Path:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = self.session_dir / f"会话_{ts}.jsonl"
        self._file = self.path.open("a", encoding="utf-8")
        return self.path

    def write(self, **fields) -> None:
        if self._file is None:
            return
        record = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), **fields}
        self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

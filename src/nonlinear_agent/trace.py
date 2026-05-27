from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TraceEvent:
    session_id: str
    event_type: str
    step: str | None = None
    tool: str | None = None
    status: str | None = None
    timestamp: float = field(default_factory=time.time)
    latency_ms: float | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TraceLogger:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def log(self, event: TraceEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False, default=str) + "\n")

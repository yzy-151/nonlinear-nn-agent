from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExperimentSession:
    session_id: str
    goal: str
    status: str = "initialized"
    current_step: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    context_summary: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)


class SessionStore:
    def __init__(self, directory: Path | str):
        self.directory = Path(directory)

    def create(self, goal: str, session_id: str) -> ExperimentSession:
        return ExperimentSession(session_id=session_id, goal=goal)

    def path_for(self, session_id: str) -> Path:
        return self.directory / f"{session_id}.json"

    def save(self, session: ExperimentSession) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for(session.session_id)
        path.write_text(json.dumps(asdict(session), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load(self, session_id: str) -> ExperimentSession:
        payload = json.loads(self.path_for(session_id).read_text(encoding="utf-8"))
        return ExperimentSession(**payload)

    def load_or_create(self, goal: str, session_id: str) -> ExperimentSession:
        path = self.path_for(session_id)
        if path.exists():
            return self.load(session_id)
        return self.create(goal=goal, session_id=session_id)

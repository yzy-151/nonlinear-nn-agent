"""Thread-safe human approval control for long-running agent roles."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ApprovalDecision:
    approval_id: str
    approved: bool
    reason: str = ""


class ApprovalController:
    def __init__(
        self,
        run_id: str,
        mode: str = "auto",
        timeout_seconds: float = 3600.0,
    ) -> None:
        if mode not in {"auto", "review"}:
            raise ValueError("approval mode must be auto or review")
        self.run_id = str(run_id)
        self.mode = mode
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self._lock = threading.Lock()
        self._pending: dict[str, dict[str, Any]] = {}

    def review(self, role: str, phase: str, payload: dict[str, Any]) -> ApprovalDecision:
        if self.mode == "auto":
            return ApprovalDecision("auto", True, "auto mode")
        approval_id = uuid.uuid4().hex[:16]
        signal = threading.Event()
        record = {
            "approval_id": approval_id,
            "run_id": self.run_id,
            "role": str(role),
            "phase": str(phase),
            "status": "pending",
            "created_at": time.time(),
            "payload": _bounded_payload(payload),
            "signal": signal,
            "decision": None,
        }
        with self._lock:
            self._pending[approval_id] = record
        if not signal.wait(self.timeout_seconds):
            with self._lock:
                self._pending.pop(approval_id, None)
            return ApprovalDecision(approval_id, False, "human review timed out")
        decision = record["decision"]
        with self._lock:
            self._pending.pop(approval_id, None)
        return decision

    def pending(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {key: value for key, value in record.items() if key not in {"signal", "decision"}}
                for record in self._pending.values()
            ]

    def decide(self, approval_id: str, approved: bool, reason: str = "") -> dict[str, Any]:
        with self._lock:
            record = self._pending.get(str(approval_id))
            if record is None:
                raise KeyError("approval request not found")
            decision = ApprovalDecision(str(approval_id), bool(approved), str(reason).strip())
            record["decision"] = decision
            record["status"] = "approved" if approved else "rejected"
            record["signal"].set()
        return asdict(decision)


def _bounded_payload(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "goal", "reason", "risk", "round_index", "hypotheses", "plan",
        "candidate_count", "candidates", "historical_best", "input", "output",
        "metrics", "usage_summary", "artifacts",
    }
    return {key: value for key, value in payload.items() if key in allowed}

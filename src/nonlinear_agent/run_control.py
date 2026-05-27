from __future__ import annotations


class RunController:
    def __init__(self) -> None:
        self._cancelled = False
        self._reason = ""

    def cancel(self, reason: str = "cancelled") -> None:
        self._cancelled = True
        self._reason = reason

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    @property
    def reason(self) -> str:
        return self._reason or "cancelled"

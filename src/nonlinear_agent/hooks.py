from __future__ import annotations

import inspect
from collections import defaultdict
from typing import Awaitable, Callable, Union

from nonlinear_agent.trace import TraceEvent

HookCallback = Callable[[TraceEvent], Union[None, Awaitable[None]]]


class HookManager:
    def __init__(self):
        self._callbacks: dict[str, list[HookCallback]] = defaultdict(list)

    def register(self, event_name: str, callback: HookCallback) -> None:
        self._callbacks[event_name].append(callback)

    async def emit(self, event_name: str, event: TraceEvent) -> None:
        for callback in self._callbacks.get(event_name, []):
            result = callback(event)
            if inspect.isawaitable(result):
                await result

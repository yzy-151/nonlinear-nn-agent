from __future__ import annotations

import asyncio
from enum import Enum


class ErrorType(str, Enum):
    VALIDATION_ERROR = "validation_error"
    TIMEOUT_ERROR = "timeout_error"
    TOOL_ERROR = "tool_error"
    METRIC_THRESHOLD_ERROR = "metric_threshold_error"
    CANCELLED = "cancelled"


def classify_exception(exc: BaseException) -> ErrorType:
    if isinstance(exc, asyncio.TimeoutError):
        return ErrorType.TIMEOUT_ERROR
    if isinstance(exc, ValueError):
        return ErrorType.VALIDATION_ERROR
    message = str(exc).lower()
    if "nmse" in message and "threshold" in message:
        return ErrorType.METRIC_THRESHOLD_ERROR
    return ErrorType.TOOL_ERROR

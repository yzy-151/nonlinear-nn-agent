"""FailureHandoff — supervisor-consumable failure specs (v3.8.x)."""

from __future__ import annotations

from dataclasses import dataclass

from nonlinear_agent.execution_agent import ExecutionResult


@dataclass(frozen=True)
class FailureSpec:
    classification: str
    retryable: bool
    suggested_action: str
    tool_name: str
    error: str


_RETRY_POLICY = {
    "timeout": (True, "retry with longer budget"),
    "oom": (False, "reduce model size or batch"),
    "nan": (True, "change hyperparameters and retry"),
    "missing_artifact": (True, "re-run training and verify artifacts"),
    "error": (False, "inspect error and revise plan"),
    "cancelled": (False, "user cancelled; do not auto-retry"),
}


class FailureHandoff:
    """Converts a failed ExecutionResult into a supervisor-consumable spec."""

    def to_spec(self, result: ExecutionResult) -> FailureSpec:
        retryable, action = _RETRY_POLICY.get(
            result.classification, (False, "inspect error and revise plan")
        )
        return FailureSpec(
            classification=result.classification,
            retryable=retryable,
            suggested_action=action,
            tool_name=result.tool_name,
            error=result.error,
        )

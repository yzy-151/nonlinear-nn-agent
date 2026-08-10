"""TDD tests for v3.8.x: FailureHandoff (supervisor-consumable failure specs)."""

from __future__ import annotations

import unittest

from nonlinear_agent.execution_agent import ExecutionAgent, ExecutionResult


class TestFailureHandoff(unittest.TestCase):
    def _result(self, classification: str) -> ExecutionResult:
        return ExecutionResult(
            status="failed",
            classification=classification,
            tool_name="run_training",
            error=f"simulated {classification}",
        )

    def test_handoff_maps_each_classification(self):
        from nonlinear_agent.failure_handoff import FailureHandoff

        handoff = FailureHandoff()
        expected = {
            "timeout": (True, "retry with longer budget"),
            "oom": (False, "reduce model size or batch"),
            "nan": (True, "change hyperparameters and retry"),
            "missing_artifact": (True, "re-run training and verify artifacts"),
            "error": (False, "inspect error and revise plan"),
        }
        for classification, (retryable, action) in expected.items():
            spec = handoff.to_spec(self._result(classification))
            self.assertEqual(spec.classification, classification)
            self.assertEqual(spec.retryable, retryable)
            self.assertEqual(spec.suggested_action, action)

    def test_handoff_spec_is_supervisor_consumable(self):
        from nonlinear_agent.failure_handoff import FailureHandoff

        spec = FailureHandoff().to_spec(self._result("timeout"))
        # supervisor graph 可以直接消费的字段
        self.assertTrue(hasattr(spec, "classification"))
        self.assertTrue(hasattr(spec, "retryable"))
        self.assertTrue(hasattr(spec, "suggested_action"))
        self.assertTrue(hasattr(spec, "tool_name"))
        self.assertTrue(hasattr(spec, "error"))


if __name__ == "__main__":
    unittest.main()

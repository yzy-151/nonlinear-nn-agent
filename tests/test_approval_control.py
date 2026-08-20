from __future__ import annotations

import threading
import time
import unittest


class ApprovalControlTest(unittest.TestCase):
    def test_auto_mode_approves_without_pending_review(self):
        from nonlinear_agent.approval import ApprovalController

        controller = ApprovalController("auto-run", mode="auto")
        decision = controller.review(
            role="idea_plan",
            phase="output",
            payload={"reason": "review proposed experiments"},
        )

        self.assertTrue(decision.approved)
        self.assertEqual(controller.pending(), [])

    def test_review_mode_blocks_until_reasoned_rejection(self):
        from nonlinear_agent.approval import ApprovalController

        controller = ApprovalController("review-run", mode="review", timeout_seconds=2)
        result = []

        worker = threading.Thread(
            target=lambda: result.append(
                controller.review(
                    role="execution",
                    phase="input",
                    payload={"risk": "starts model training", "input": {"epochs": 50}},
                )
            )
        )
        worker.start()
        for _ in range(20):
            if controller.pending():
                break
            time.sleep(0.01)
        approval_id = controller.pending()[0]["approval_id"]

        controller.decide(
            approval_id,
            approved=False,
            reason="Reduce epochs and explain the parameter budget.",
        )
        worker.join(timeout=1)

        self.assertFalse(result[0].approved)
        self.assertIn("Reduce epochs", result[0].reason)
        self.assertEqual(controller.pending(), [])


if __name__ == "__main__":
    unittest.main()

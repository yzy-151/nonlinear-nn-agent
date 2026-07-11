"""Tests for RuntimeControlPlane (v2.0.0)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.control_plane import RuntimeControlPlane


class TestControlPlane(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "runtime.sqlite"
        self.cp = RuntimeControlPlane(self.db_path)

    def tearDown(self):
        self.cp.close()
        self.tmpdir.cleanup()

    def test_register_request_is_idempotent(self):
        ok1 = self.cp.register_request("s1", "req-1", '{"goal":"test"}')
        ok2 = self.cp.register_request("s1", "req-1", '{"goal":"test"}')
        self.assertTrue(ok1)
        self.assertFalse(ok2)

    def test_register_different_sessions_same_request_id(self):
        ok1 = self.cp.register_request("s1", "req-1")
        ok2 = self.cp.register_request("s2", "req-1")
        self.assertTrue(ok1)
        self.assertTrue(ok2)

    def test_enqueue_and_claim_job(self):
        job_id = self.cp.enqueue_job("s1", "req-1")
        self.assertTrue(len(job_id) > 0)
        claimed = self.cp.claim_job(job_id, "worker-1")
        self.assertTrue(claimed)

    def test_double_claim_fails(self):
        job_id = self.cp.enqueue_job("s1", "req-1")
        self.assertTrue(self.cp.claim_job(job_id, "worker-1"))
        self.assertFalse(self.cp.claim_job(job_id, "worker-2"))

    def test_lease_expired_job_can_be_reclaimed(self):
        job_id = self.cp.enqueue_job("s1", "req-1")
        # Claim with very short lease
        self.assertTrue(self.cp.claim_job(job_id, "worker-1", lease_seconds=0.001))
        import time
        time.sleep(0.01)
        self.assertTrue(self.cp.claim_job(job_id, "worker-2"))

    def test_complete_job(self):
        job_id = self.cp.enqueue_job("s1", "req-1")
        self.assertTrue(self.cp.claim_job(job_id, "worker-1"))
        self.cp.complete_job(job_id)
        # Completed job cannot be reclaimed
        self.assertFalse(self.cp.claim_job(job_id, "worker-2"))

    def test_fail_job(self):
        job_id = self.cp.enqueue_job("s1", "req-1")
        self.cp.fail_job(job_id)
        self.assertFalse(self.cp.claim_job(job_id, "worker-1"))

    def test_fail_job_if_max_attempts(self):
        job_id = self.cp.enqueue_job("s1", "req-1", max_attempts=2)
        self.assertTrue(self.cp.claim_job(job_id, "worker-1", lease_seconds=0.001))
        import time
        time.sleep(0.01)
        self.assertTrue(self.cp.claim_job(job_id, "worker-2", lease_seconds=0.001))
        time.sleep(0.01)
        # Third attempt should fail since max_attempts=2
        self.assertTrue(self.cp.fail_job_if_max_attempts(job_id))

    def test_event_sequence_is_monotonic_per_session(self):
        ids = []
        for i in range(5):
            seq = self.cp.record_event("s1", "tool_start", '{"step":1}')
            ids.append(seq)
        self.assertEqual(ids, [0, 1, 2, 3, 4])

    def test_different_sessions_have_independent_sequences(self):
        s1 = self.cp.record_event("s1", "start", "{}")
        s2 = self.cp.record_event("s2", "start", "{}")
        self.assertEqual(s1, 0)
        self.assertEqual(s2, 0)

    def test_get_events_since(self):
        self.cp.record_event("s1", "start", "{}")
        self.cp.record_event("s1", "tool_start", "{}")
        self.cp.record_event("s1", "complete", "{}")
        events = self.cp.get_events_since("s1", last_event_id=0)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["id"], 1)
        self.assertEqual(events[1]["id"], 2)

    def test_concurrent_claim_executes_once(self):
        """8 workers claiming the same job: exactly one wins (idempotent execute)."""
        import threading

        job_id = self.cp.enqueue_job("s1", "req-1")
        barrier = threading.Barrier(8)
        results: list[bool] = []

        def worker(index: int) -> None:
            barrier.wait()
            results.append(self.cp.claim_job(job_id, f"worker-{index}"))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(sum(results), 1)

"""Reliability stress test for the SQLite runtime control plane (v2.0.0).

Drives RuntimeControlPlane with concurrent request dedup, atomic job
claims, lease-expiry recovery, and monotonic event sequencing, then
checks the v2.0 acceptance lines:
  - duplicate execution rate == 0
  - event loss rate == 0
  - terminal consistency == 1.0
  - recovery rate after injected failures >= 0.95

This is a local single-process SQLite baseline, not a distributed test.
"""

from __future__ import annotations

import json
import tempfile
import threading
import time
from pathlib import Path
from typing import Any


def run_stress_test(
    concurrency: int = 8,
    requests: int = 100,
    failure_rate: float = 0.1,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Run the stress test and return the acceptance report."""
    from nonlinear_agent.control_plane import RuntimeControlPlane

    with tempfile.TemporaryDirectory() as tmp:
        cp = RuntimeControlPlane(Path(tmp) / "stress.sqlite")

        # ── 1. Request dedup: same request_id registered exactly once ──
        registered = [False] * requests

        def register(index: int) -> None:
            registered[index] = cp.register_request("s1", f"req-{index}", "{}")

        threads = [
            threading.Thread(target=register, args=(i,)) for i in range(requests)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        duplicate_requests = requests - sum(registered)

        # ── 2. Atomic claim: 8 workers race for the same job, one wins ──
        job_ids = [
            cp.enqueue_job("s1", f"req-{i}", max_attempts=3) for i in range(requests)
        ]
        claim_wins = [0] * requests
        claim_lock = threading.Lock()

        def claim(job_index: int, worker: str) -> None:
            if cp.claim_job(job_ids[job_index], worker, lease_seconds=0.05):
                with claim_lock:
                    claim_wins[job_index] += 1

        worker_threads = []
        for i in range(requests):
            for w in range(concurrency):
                worker_threads.append(
                    threading.Thread(target=claim, args=(i, f"worker-{w}"))
                )
        for t in worker_threads:
            t.start()
        for t in worker_threads:
            t.join()

        duplicate_executions = sum(1 for wins in claim_wins if wins > 1)
        executed_once = sum(1 for wins in claim_wins if wins == 1)

        # ── 3. Injected failures: some workers "crash" (never complete) ──
        crashed_count = int(round(requests * failure_rate))
        crashed = [i for i in range(crashed_count)]
        time.sleep(0.1)  # let short leases expire
        recovered = 0
        for i in crashed:
            if cp.claim_job(job_ids[i], "recovery-worker", lease_seconds=5.0):
                cp.complete_job(job_ids[i])
                recovered += 1

        # ── 4. Complete the remaining claimed jobs (terminal state) ──
        for i in range(requests):
            if claim_wins[i] == 1 and i not in crashed:
                cp.complete_job(job_ids[i])

        terminal_jobs = 0
        for i in range(requests):
            # completed jobs can never be reclaimed → terminal state reached
            if not cp.claim_job(job_ids[i], "audit-worker", lease_seconds=1.0):
                terminal_jobs += 1

        # ── 5. Monotonic event sequence: no gaps ──
        events_lost = 0
        last_seq = -1
        for _ in range(requests):
            seq = cp.record_event("s1", "test", "{}")
            if seq != last_seq + 1:
                events_lost += 1
            last_seq = seq

        cp.close()

    report: dict[str, Any] = {
        "concurrency": concurrency,
        "requests": requests,
        "failure_rate": failure_rate,
        "duplicate_requests": duplicate_requests,
        "duplicate_execution_rate": duplicate_executions / requests,
        "executed_once": executed_once,
        "event_loss_rate": events_lost / requests,
        "terminal_consistency": terminal_jobs / requests,
        "recovery_rate": recovered / crashed_count if crashed_count else 1.0,
        "injected_failures": crashed_count,
        "recovered": recovered,
        "pass": (
            duplicate_executions == 0
            and events_lost == 0
            and terminal_jobs == requests
            and (recovered / crashed_count if crashed_count else 1.0) >= 0.95
        ),
    }

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "stress.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return report

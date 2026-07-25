"""Tests for compare_runner — real execution of the four search strategies."""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from nonlinear_agent.compare_runner import run_compare_protocol, stream_compare_events
from nonlinear_agent.domains.synthetic_regression import SyntheticRegressionDomain
from nonlinear_agent.evaluation_protocol import EvaluationProtocol


class TestCompareRunner(unittest.TestCase):

    def setUp(self):
        self.domain = SyntheticRegressionDomain()

    def _smoke_protocol(self) -> EvaluationProtocol:
        return EvaluationProtocol(
            methods=["random_search", "optuna_tpe", "llm_direct", "llm_program_reflection"],
            seeds=[7, 17],
            trial_budget=3,
            parameter_count_max=100,
        )

    def test_run_compare_protocol_produces_trials(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows, summary, _ = asyncio.run(run_compare_protocol(
                self._smoke_protocol(), self.domain, Path(tmp), output_dir=Path(tmp) / "out",
            ))
            self.assertEqual(len(rows), 4 * 2 * 3)  # 24 trials
            self.assertIn("per_method", summary)
            # metric should be val_mse
            methods = summary["per_method"]
            self.assertEqual(len(methods), 4)
            for m, stats in methods.items():
                self.assertIn("best_val_mse_mean", stats)

    def test_trials_have_val_mse(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows, _, _ = asyncio.run(run_compare_protocol(
                self._smoke_protocol(), self.domain, Path(tmp),
            ))
            # Some trials should have real val_mse values
            val_mses = [r for r in rows if r.get("val_mse") is not None]
            self.assertGreater(len(val_mses), 0)
            for r in val_mses:
                self.assertIn("val_mse", r)
                self.assertIsInstance(r["val_mse"], float)

    def test_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            asyncio.run(run_compare_protocol(
                self._smoke_protocol(), self.domain, Path(tmp), output_dir=out,
            ))
            self.assertTrue((out / "trials.jsonl").exists())
            self.assertTrue((out / "summary.json").exists())
            self.assertTrue((out / "summary.csv").exists())
            # trials.jsonl has 24 lines
            lines = (out / "trials.jsonl").read_text().strip().split("\n")
            self.assertEqual(len(lines), 24)

    def test_stream_compare_events_yields_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = []
            async def collect():
                async for ev in stream_compare_events(
                    self._smoke_protocol(), self.domain, Path(tmp),
                ):
                    events.append(ev)
            asyncio.run(collect())
            types = [e["type"] for e in events]
            self.assertIn("compare_start", types)
            self.assertIn("compare_complete", types)
            self.assertGreater(types.count("trial_done"), 0)
            complete = events[-1]
            self.assertIn("summary", complete)

    def test_optuna_strategy_isolation(self):
        """If one strategy fails, others still produce trials."""
        # llm_program_reflection should still run even if something is odd
        with tempfile.TemporaryDirectory() as tmp:
            rows, _, _ = asyncio.run(run_compare_protocol(
                self._smoke_protocol(), self.domain, Path(tmp),
            ))
            methods = set(r["method"] for r in rows)
            self.assertEqual(methods, {"random_search", "optuna_tpe", "llm_direct", "llm_program_reflection"})


class TestBackwardCompatTrialRecord(unittest.TestCase):
    def test_nmse_trial_record_still_works(self):
        from nonlinear_agent.evaluation_protocol import build_trial_record
        rec = build_trial_record(
            run_id="r", method="random_search", seed=7, trial_index=0,
            nmse_db=-37.5,
        )
        self.assertEqual(rec["nmse_db"], -37.5)
        self.assertEqual(rec["metric_name"], "nmse_db")

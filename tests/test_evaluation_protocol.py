"""Tests for evaluation protocol (v1.9.0)."""

from __future__ import annotations

import unittest

from nonlinear_agent.evaluation_protocol import (
    EvaluationProtocol,
    build_full_protocol,
    build_smoke_protocol,
    build_trial_record,
)


class TestEvaluationProtocol(unittest.TestCase):

    def test_full_protocol_estimates_200_trials(self):
        p = build_full_protocol()
        self.assertEqual(p.estimate_total_trials(), 200)

    def test_smoke_protocol_estimates_24_trials(self):
        p = build_smoke_protocol()
        self.assertEqual(p.estimate_total_trials(), 24)

    def test_full_protocol_has_4_methods_5_seeds_10_budget(self):
        p = build_full_protocol()
        self.assertEqual(len(p.methods), 4)
        self.assertEqual(len(p.seeds), 5)
        self.assertEqual(p.trial_budget, 10)

    def test_smoke_protocol_has_4_methods_2_seeds_3_budget(self):
        p = build_smoke_protocol()
        self.assertEqual(len(p.methods), 4)
        self.assertEqual(len(p.seeds), 2)
        self.assertEqual(p.trial_budget, 3)

    def test_protocol_to_dict_includes_all_fields(self):
        p = build_full_protocol()
        d = p.to_dict()
        for key in ("methods", "seeds", "trial_budget", "parameter_count_max",
                     "nmse_threshold_db", "estimated_total_trials"):
            self.assertIn(key, d)

    def test_trial_record_has_all_required_fields(self):
        record = build_trial_record(
            run_id="test-1",
            method="random_search",
            seed=7,
            trial_index=1,
        )
        required = {
            "run_id", "method", "seed", "trial_index",
            "nmse_db", "target_hit", "rejected", "runtime_failed",
            "reflection_used",
        }
        for field in required:
            self.assertIn(field, record)

    def test_custom_protocol_estimates_correctly(self):
        p = EvaluationProtocol(
            methods=["random_search"],
            seeds=[42],
            trial_budget=5,
        )
        self.assertEqual(p.estimate_total_trials(), 5)

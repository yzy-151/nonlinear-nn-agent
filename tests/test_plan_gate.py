"""TDD tests for v3.7.0 PlanGate: IdeaPlanSpec schema + dedup + citations."""

from __future__ import annotations

import unittest


def _valid_plan() -> dict:
    return {
        "plan_id": "plan-001",
        "hypotheses": [
            {
                "hypothesis": "larger memory depth improves NMSE",
                "rationale": "history shows memory scaling helps",
                "citation": "handoff/llm-continuation-plan.md#8. DeepSeek self-correction case",
            }
        ],
        "candidate_experiments": [
            {
                "model_type": "tiny_mlp",
                "memory_depth": 16,
                "params_estimate": 1200,
                "budget": {"parameter_count_max": 20000, "epochs_max": 100},
                "stop_condition": "nmse <= -37 dB or epochs exhausted",
                "rationale": "known-best neighborhood",
                "citation": "docs/experiments/nonlinear-search-ablation-v2.md",
            }
        ],
        "experiment_dag": {"nodes": ["exp_001"], "edges": []},
        "expected_information_gain": 0.6,
        "risk": "low",
        "fallback": [{"model_type": "complex_lstsq", "memory_depth": 24}],
        "required_code_changes": [],
        "no_code_change_candidates": ["tiny_mlp"],
    }


def _batch_plan(count: int = 3) -> dict:
    plan = _valid_plan()
    plan["candidate_experiments"] = [
        {
            **plan["candidate_experiments"][0],
            "experiment_id": f"round-1-exp-{index + 1}",
            "model_type": f"unseen_model_{index + 1}",
            "exploration_role": "explore" if index < 2 else "exploit",
            "based_on_fact_refs": [],
            "expected_information_gain": 0.7 - index * 0.1,
        }
        for index in range(count)
    ]
    return plan


class TestPlanGate(unittest.TestCase):
    def test_valid_plan_passes(self):
        from nonlinear_agent.plan_gate import PlanGate

        gate = PlanGate()
        self.assertEqual(gate.validate(_valid_plan()), [])

    def test_missing_candidate_fields_rejected(self):
        from nonlinear_agent.plan_gate import PlanGate

        plan = _valid_plan()
        del plan["candidate_experiments"][0]["params_estimate"]
        errors = PlanGate().validate(plan)
        self.assertTrue(any("params_estimate" in e for e in errors))

    def test_candidate_without_budget_rejected(self):
        from nonlinear_agent.plan_gate import PlanGate

        plan = _valid_plan()
        del plan["candidate_experiments"][0]["budget"]
        errors = PlanGate().validate(plan)
        self.assertTrue(any("budget" in e for e in errors))

    def test_candidate_without_stop_condition_rejected(self):
        from nonlinear_agent.plan_gate import PlanGate

        plan = _valid_plan()
        del plan["candidate_experiments"][0]["stop_condition"]
        errors = PlanGate().validate(plan)
        self.assertTrue(any("stop_condition" in e for e in errors))

    def test_duplicate_config_hash_rejected(self):
        from nonlinear_agent.plan_gate import PlanGate

        plan = _valid_plan()
        history = {
            "known-hash-1",
        }
        duplicate = plan["candidate_experiments"][0] | {"config_hash": "known-hash-1"}
        plan["candidate_experiments"] = [duplicate]
        self.assertTrue(PlanGate().is_duplicate(plan, history))

    def test_citation_coverage_at_least_0_90(self):
        from nonlinear_agent.plan_gate import PlanGate

        gate = PlanGate()
        plan = _valid_plan()
        self.assertGreaterEqual(gate.citation_coverage(plan), 0.90)

    def test_budget_violation_rejected(self):
        from nonlinear_agent.plan_gate import PlanGate

        plan = _valid_plan()
        plan["candidate_experiments"][0]["params_estimate"] = 50000
        errors = PlanGate().validate(plan, parameter_count_max=20000)
        self.assertTrue(any("budget" in e.lower() or "params" in e.lower() for e in errors))

    def test_batch_contract_requires_exactly_three_unique_experiments(self):
        from nonlinear_agent.plan_gate import PlanGate

        gate = PlanGate()
        self.assertEqual(
            gate.validate_batch(_batch_plan(), expected_experiments=3), []
        )

        too_short = gate.validate_batch(_batch_plan(2), expected_experiments=3)
        self.assertTrue(any("exactly 3" in error for error in too_short))

        duplicate = _batch_plan()
        duplicate["candidate_experiments"][1]["experiment_id"] = (
            duplicate["candidate_experiments"][0]["experiment_id"]
        )
        errors = gate.validate_batch(duplicate, expected_experiments=3)
        self.assertTrue(any("experiment_id must be unique" in error for error in errors))

    def test_later_round_candidates_must_reference_prior_facts(self):
        from nonlinear_agent.plan_gate import PlanGate

        plan = _batch_plan()
        available = {"fact:round-1:best", "fact:round-1:failure"}
        for candidate in plan["candidate_experiments"]:
            candidate["based_on_fact_refs"] = ["fact:round-1:best"]

        self.assertEqual(
            PlanGate().validate_batch(
                plan,
                expected_experiments=3,
                round_index=2,
                available_fact_refs=available,
            ),
            [],
        )

        plan["candidate_experiments"][1]["based_on_fact_refs"] = ["fact:unknown"]
        errors = PlanGate().validate_batch(
            plan,
            expected_experiments=3,
            round_index=2,
            available_fact_refs=available,
        )
        self.assertTrue(any("unknown fact ref" in error for error in errors))

    def test_batch_rejects_citations_outside_retrieved_allowlist(self):
        from nonlinear_agent.plan_gate import PlanGate

        plan = _batch_plan()
        plan["hypotheses"][0]["citation"] = "knowledge:known-prior"
        for candidate in plan["candidate_experiments"]:
            candidate["citation"] = "memory:verified-run"

        self.assertEqual(
            PlanGate().validate_batch(
                plan,
                expected_experiments=3,
                available_citation_ids={
                    "knowledge:known-prior",
                    "memory:verified-run",
                },
            ),
            [],
        )

        plan["candidate_experiments"][1]["citation"] = "knowledge:invented"
        errors = PlanGate().validate_batch(
            plan,
            expected_experiments=3,
            available_citation_ids={
                "knowledge:known-prior",
                "memory:verified-run",
            },
        )
        self.assertTrue(any("unknown citation" in error for error in errors))

    def test_single_plan_rejects_citations_outside_retrieved_allowlist(self):
        from nonlinear_agent.plan_gate import PlanGate

        plan = _valid_plan()
        errors = PlanGate().validate(
            plan,
            available_citation_ids={"knowledge:allowed"},
        )

        self.assertTrue(any("unknown citation" in error for error in errors))

    def test_retrieved_allowlist_rejects_empty_citations(self):
        from nonlinear_agent.plan_gate import PlanGate

        plan = _valid_plan()
        plan["hypotheses"][0]["citation"] = ""
        plan["candidate_experiments"][0]["citation"] = "   "

        errors = PlanGate().validate(
            plan,
            available_citation_ids={"knowledge:allowed"},
        )

        self.assertTrue(any("hypotheses[0] empty citation" in error for error in errors))
        self.assertTrue(
            any("candidate_experiments[0] empty citation" in error for error in errors)
        )


class TestPlanningTasksSchemaValidity(unittest.TestCase):
    """v3.7.0 acceptance: 12 planning tasks must all be schema-valid."""

    TASKS = [
        {"goal": "reach -35 dB under 4000 params", "model": "tiny_mlp"},
        {"goal": "explore spline_mlp knots", "model": "spline_mlp"},
        {"goal": "compare lstsq memory depths", "model": "complex_lstsq"},
        {"goal": "find cheaper activation", "model": "tiny_mlp"},
        {"goal": "sweep learning rate", "model": "tiny_mlp"},
        {"goal": "verify artifact flow", "model": "linear"},
        {"goal": "reduce parameter count", "model": "complex_cnn"},
        {"goal": "improve reflection recovery", "model": "tiny_mlp"},
        {"goal": "budget edge candidate", "model": "spline_mlp"},
        {"goal": "multi-round self correction", "model": "tiny_mlp"},
        {"goal": "long history stability", "model": "complex_lstsq"},
        {"goal": "cross-domain transfer check", "model": "linear"},
    ]

    def test_all_12_tasks_are_schema_valid(self):
        from nonlinear_agent.plan_gate import PlanGate

        gate = PlanGate()
        for task in self.TASKS:
            plan = _valid_plan()
            plan["plan_id"] = f"plan-{task['model']}"
            plan["candidate_experiments"][0]["model_type"] = task["model"]
            plan["candidate_experiments"][0]["rationale"] = task["goal"]
            errors = gate.validate(plan, parameter_count_max=20000)
            self.assertEqual(
                errors, [], f"task {task['goal']} not schema-valid: {errors}"
            )


class TestPlanHandoff(unittest.TestCase):
    def test_handoff_projects_candidates_to_execution_steps(self):
        from nonlinear_agent.plan_handoff import PlanHandoff

        steps = PlanHandoff().to_execution(_valid_plan())
        self.assertEqual(len(steps), 1)
        step = steps[0]
        self.assertEqual(step.overrides["model_type"], "tiny_mlp")
        self.assertEqual(step.budget["parameter_count_max"], 20000)
        self.assertEqual(step.stop_condition, "nmse <= -37 dB or epochs exhausted")
        self.assertEqual(len(step.config_hash), 64)
        self.assertEqual(step.citations, ("docs/experiments/nonlinear-search-ablation-v2.md",))

    def test_handoff_keeps_explicit_config_hash(self):
        from nonlinear_agent.plan_handoff import PlanHandoff

        plan = _valid_plan()
        plan["candidate_experiments"][0]["config_hash"] = "known-hash"
        step = PlanHandoff().to_execution(plan)[0]
        self.assertEqual(step.config_hash, "known-hash")


if __name__ == "__main__":
    unittest.main()

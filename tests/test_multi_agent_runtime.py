from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from tests.test_supervisor_e2e import _plan, _three_candidate_plan


class TestMultiAgentRuntime(unittest.TestCase):
    def test_generated_candidate_has_a_separate_epoch_ceiling(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        plan = _three_candidate_plan(1)
        candidate = plan["candidate_experiments"][0]
        candidate["implementation_source"] = "generated_plugin"
        candidate["config"] = {"epochs": 300, "width": 16}
        candidate["budget"] = {"parameter_count_max": 13000, "epochs_max": 300}
        runtime = MultiAgentRuntime(
            Path.cwd(), object(), object(), object(),
            candidate_epochs_max=10000,
            generated_candidate_epochs_max=50,
        )

        with self.assertRaisesRegex(ValueError, "generated model epochs 300 exceeds"):
            runtime._apply_run_policy(plan)

    def test_run_policy_can_require_open_coding_candidates(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        plan = _three_candidate_plan(1)
        for candidate in plan["candidate_experiments"]:
            candidate.update(
                {
                    "implementation_source": "registered_model",
                    "model_type": "tiny_mlp",
                    "config": {
                        "model_type": "tiny_mlp",
                        "feature_mode": "complex_mp",
                        "memory_depth": 4,
                        "mp_order_count": 2,
                        "hidden_units": 16,
                        "activation": "relu",
                        "epochs": 10,
                    },
                }
            )
        runtime = MultiAgentRuntime(
            Path.cwd(), object(), object(), object(),
            registered_model_catalog={"tiny_mlp": {"description": "known"}},
            min_generated_candidates_per_round=2,
        )

        with self.assertRaisesRegex(ValueError, "generated_plugin candidate minimum"):
            runtime._apply_run_policy(plan)

    def test_run_policy_allows_only_one_high_fidelity_candidate_in_selected_round(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        plan = _three_candidate_plan(1)
        for candidate in plan["candidate_experiments"]:
            candidate.update(
                {
                    "implementation_source": "registered_model",
                    "model_type": "tiny_mlp",
                    "config": {
                        "model_type": "tiny_mlp",
                        "feature_mode": "complex_mp",
                        "memory_depth": 8,
                        "mp_order_count": 2,
                        "hidden_units": 32,
                        "activation": "relu",
                        "epochs": 10000,
                    },
                    "budget": {"parameter_count_max": 13000, "epochs_max": 10000},
                }
            )
        runtime = MultiAgentRuntime(
            Path.cwd(), object(), object(), object(),
            registered_model_catalog={"tiny_mlp": {"description": "known"}},
            candidate_parameter_count_max=13000,
            candidate_epochs_max=10000,
            screening_epochs_max=300,
            high_fidelity_rounds=(1,),
            max_high_fidelity_candidates_per_round=1,
        )

        with self.assertRaisesRegex(ValueError, "high-fidelity candidate limit"):
            runtime._apply_run_policy(plan, round_index=1)
        with self.assertRaisesRegex(ValueError, "screening epoch limit"):
            runtime._apply_run_policy(plan, round_index=2)

    def test_planner_repairs_multiple_registered_tool_policy_errors(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        over_budget = _three_candidate_plan(1)
        over_budget["candidate_experiments"][0].update(
            {
                "implementation_source": "registered_model",
                "model_type": "missing_spline_tool",
                "config": {
                    "model_type": "missing_spline_tool",
                    "feature_mode": "complex_mp",
                    "memory_depth": 20,
                    "mp_order_count": 3,
                    "hidden_units": 96,
                    "spline_knots": 16,
                    "spline_range": 3.0,
                    "epochs": 100,
                },
                "budget": {"parameter_count_max": 13000, "epochs_max": 100},
            }
        )
        over_budget["candidate_experiments"][1].update(
            {
                "implementation_source": "registered_model",
                "model_type": "missing_cnn_tool",
                "config": {
                    "model_type": "missing_cnn_tool",
                    "feature_mode": "complex_mp",
                    "memory_depth": 20,
                    "mp_order_count": 3,
                    "kernel_size": 3,
                    "num_layers": 2,
                    "epochs": 100,
                },
                "budget": {"parameter_count_max": 13000, "epochs_max": 100},
            }
        )
        repaired = json.loads(json.dumps(over_budget))
        repaired["candidate_experiments"][0].update(
            {
                "model_type": "tiny_mlp",
                "config": {
                    "model_type": "tiny_mlp",
                    "feature_mode": "complex_mp",
                    "memory_depth": 8,
                    "mp_order_count": 2,
                    "hidden_units": 32,
                    "activation": "relu",
                    "epochs": 100,
                },
            }
        )
        repaired["candidate_experiments"][1].update(
            {
                "model_type": "tiny_mlp",
                "config": {
                    "model_type": "tiny_mlp",
                    "feature_mode": "complex_mp",
                    "memory_depth": 8,
                    "mp_order_count": 2,
                    "hidden_units": 32,
                    "activation": "relu",
                    "epochs": 100,
                },
            }
        )

        class Router:
            def __init__(self):
                self.responses = [over_budget, repaired]
                self.prompts = []

            def complete(self, role, prompt):
                self.prompts.append(prompt)
                return json.dumps(self.responses.pop(0))

        router = Router()
        runtime = MultiAgentRuntime(
            Path.cwd(), router, object(), object(),
            registered_model_catalog={
                "spline_mlp": {"description": "known"},
                "complex_cnn": {"description": "known"},
                "tiny_mlp": {"description": "known"},
            },
            candidate_parameter_count_max=13000,
            candidate_epochs_max=100,
        )

        result = runtime._idea_plan(
            {
                "run_id": "repair-budget-plan",
                "goal": "reach target",
                "round_index": 1,
                "rounds_total": 1,
                "experiments_per_round": 3,
                "available_fact_refs": [],
                "round_records": [],
            }
        )

        self.assertEqual(len(router.prompts), 2)
        self.assertGreaterEqual(router.prompts[1].count("not in the registered model catalog"), 2)
        candidate = result["candidate_experiments"][0]
        self.assertEqual(candidate["config"]["hidden_units"], 32)

    def test_planner_uses_configured_repairs_until_plan_passes_policy(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        invalid = _three_candidate_plan(1)
        invalid["candidate_experiments"][1]["implementation_source"] = "invalid_source"
        repaired = json.loads(json.dumps(invalid))
        repaired["candidate_experiments"][1]["implementation_source"] = "generated_plugin"

        class Router:
            def __init__(self):
                self.responses = [invalid, invalid, repaired]
                self.prompts = []

            def complete(self, role, prompt):
                self.prompts.append(prompt)
                return json.dumps(self.responses.pop(0))

        router = Router()
        runtime = MultiAgentRuntime(
            Path.cwd(),
            router,
            object(),
            object(),
            registered_model_catalog={"tiny_mlp": {"description": "known"}},
            candidate_parameter_count_max=13000,
            candidate_epochs_max=100,
            planner_max_repairs=2,
        )

        result = runtime._idea_plan(
            {
                "run_id": "repair-plan-twice",
                "goal": "reach target",
                "round_index": 2,
                "rounds_total": 10,
                "experiments_per_round": 3,
                "available_fact_refs": ["fact:round-1:best:r1-candidate-1"],
                "round_records": [],
            }
        )

        self.assertEqual(len(router.prompts), 3)
        self.assertEqual(
            result["candidate_experiments"][1]["implementation_source"],
            "generated_plugin",
        )

    def test_registered_candidate_is_projected_into_parameter_budget(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime
        from nonlinear_agent.planner_validation import estimate_parameter_count

        plan = _three_candidate_plan(1)
        plan["candidate_experiments"][0].update(
            {
                "implementation_source": "registered_model",
                "model_type": "tiny_mlp",
                "config": {
                    "model_type": "tiny_mlp",
                    "feature_mode": "complex_mp",
                    "memory_depth": 20,
                    "mp_order_count": 3,
                    "hidden_units": 112,
                    "activation": "relu",
                    "epochs": 100,
                },
                "budget": {"parameter_count_max": 13000, "epochs_max": 100},
            }
        )
        runtime = MultiAgentRuntime(
            Path.cwd(),
            object(),
            object(),
            object(),
            registered_model_catalog={"tiny_mlp": {"description": "known"}},
            candidate_parameter_count_max=13000,
            candidate_epochs_max=100,
        )

        result = runtime._apply_run_policy(plan, round_index=1)
        candidate = result["candidate_experiments"][0]

        self.assertLessEqual(estimate_parameter_count(candidate["config"]), 13000)
        self.assertLess(candidate["config"]["hidden_units"], 112)
        self.assertEqual(candidate["runtime_policy_repairs"][0]["field"], "hidden_units")
        self.assertEqual(candidate["runtime_policy_repairs"][0]["original"], 112)

    def test_registered_candidate_vocabulary_is_canonicalized(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        plan = _three_candidate_plan(1)
        plan["candidate_experiments"][0].update(
            {
                "implementation_source": "registered_model",
                "model_type": "tiny_mlp",
                "config": {
                    "model_type": "tiny_mlp",
                    "feature_mode": "real_imag",
                    "memory_depth": 8,
                    "mp_order_count": 2,
                    "hidden_units": 32,
                    "activation": "relu",
                    "epochs": 20,
                },
                "budget": {"parameter_count_max": 13000, "epochs_max": 20},
            }
        )
        runtime = MultiAgentRuntime(
            Path.cwd(),
            object(),
            object(),
            object(),
            registered_model_catalog={"tiny_mlp": {"description": "known"}},
            candidate_parameter_count_max=13000,
            candidate_epochs_max=20,
        )

        result = runtime._apply_run_policy(plan, round_index=1)
        candidate = result["candidate_experiments"][0]

        self.assertEqual(candidate["config"]["feature_mode"], "complex_mp")
        repair = candidate["runtime_policy_repairs"][0]
        self.assertEqual(repair["kind"], "vocabulary_canonicalization")
        self.assertEqual(repair["original"], "real_imag")

    def test_failed_candidate_report_marks_architecture_unverified_not_unknown(self):
        from nonlinear_agent.multi_agent_runtime import _outcome_report_record

        record = _outcome_report_record(
            {
                "experiment_id": "r1-candidate-2",
                "candidate_name": "ResMLP",
                "candidate": {"model_type": "ResMLP", "config": {"width": 16}},
                "status": "failed",
                "metrics": {},
                "execution_result": {"status": "failed", "classification": "coding_error"},
            },
            -41.0,
        )

        self.assertEqual(record["model_type"], "ResMLP")
        self.assertEqual(record["architecture_status"], "unverified")
        self.assertEqual(record["model_descriptor"]["name"], "unverified:ResMLP")
        self.assertEqual(
            record["model_descriptor"]["nodes"][0]["operation"],
            "no_executable_architecture",
        )

    def test_planner_can_autonomously_select_catalog_model_with_run_limits(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        plan = _three_candidate_plan(1)
        plan["candidate_experiments"][0].update(
            {
                "implementation_source": "registered_model",
                "model_type": "tiny_mlp",
                "config": {
                    "model_type": "tiny_mlp",
                    "feature_mode": "complex_mp",
                    "target_mode": "direct",
                    "memory_depth": 20,
                    "mp_order_count": 3,
                    "hidden_units": 96,
                    "activation": "relu",
                    "epochs": 10000,
                },
                "budget": {
                    "parameter_count_max": 999999,
                    "epochs_max": 999999,
                    "timeout_seconds": 999999,
                },
            }
        )

        class Router:
            def __init__(self):
                self.prompt = ""

            def complete(self, role, prompt):
                self.prompt = prompt
                return json.dumps(plan)

        router = Router()
        runtime = MultiAgentRuntime(
            Path.cwd(),
            router,
            object(),
            object(),
            registered_model_catalog={
                "tiny_mlp": {
                    "description": "registered compact MLP over complex MP features",
                    "config_fields": ["memory_depth", "mp_order_count", "hidden_units"],
                }
            },
            candidate_parameter_count_max=13000,
            candidate_epochs_max=10000,
            candidate_timeout_seconds=1800,
        )

        result = runtime._idea_plan(
            {
                "run_id": "catalog-plan",
                "goal": "reach -41 dB",
                "round_index": 1,
                "rounds_total": 10,
                "experiments_per_round": 3,
                "available_fact_refs": [],
                "round_records": [],
            }
        )

        self.assertIn("registered compact MLP", router.prompt)
        self.assertIn('"parameter_count_max": 13000', router.prompt)
        selected = result["candidate_experiments"][0]
        self.assertEqual(selected["implementation_source"], "registered_model")
        self.assertEqual(selected["budget"]["parameter_count_max"], 13000)
        self.assertEqual(selected["budget"]["epochs_max"], 10000)
        self.assertEqual(selected["budget"]["timeout_seconds"], 1800.0)

    def test_planner_rejects_unregistered_model_tool_selection(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        plan = _three_candidate_plan(1)
        plan["candidate_experiments"][0]["implementation_source"] = "registered_model"
        plan["candidate_experiments"][0]["model_type"] = "invented_backend"

        class Router:
            def complete(self, role, prompt):
                return json.dumps(plan)

        runtime = MultiAgentRuntime(
            Path.cwd(), Router(), object(), object(),
            registered_model_catalog={"tiny_mlp": {"description": "known"}},
        )

        with self.assertRaisesRegex(ValueError, "not in the registered model catalog"):
            runtime._idea_plan(
                {
                    "run_id": "bad-catalog-plan",
                    "goal": "reach target",
                    "round_index": 1,
                    "rounds_total": 1,
                    "experiments_per_round": 3,
                    "available_fact_refs": [],
                    "round_records": [],
                }
            )

    def test_idea_plan_contract_exposes_verified_registered_anchor(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        plan = _three_candidate_plan(1)

        class Router:
            def __init__(self):
                self.prompt = ""

            def complete(self, role, prompt):
                self.prompt = prompt
                return json.dumps(plan)

        router = Router()
        runtime = MultiAgentRuntime(
            Path.cwd(),
            router,
            object(),
            object(),
            registered_anchor={
                "model_type": "tiny_mlp",
                "config": {
                    "memory_depth": 5,
                    "mp_order_count": 5,
                    "hidden_units": 80,
                    "epochs": 12000,
                },
                "parameter_count_max": 6000,
                "timeout_seconds": 1800,
            },
        )

        result = runtime._idea_plan(
            {
                "run_id": "anchor-plan",
                "goal": "reach -40 dB",
                "round_index": 1,
                "rounds_total": 1,
                "experiments_per_round": 3,
                "available_fact_refs": [],
                "round_records": [],
            }
        )

        self.assertIn('"implementation_source": "registered_model"', router.prompt)
        self.assertIn('"epochs": 12000', router.prompt)
        self.assertIn("include this exact verified anchor", router.prompt)
        anchor = result["candidate_experiments"][0]
        self.assertEqual(anchor["implementation_source"], "registered_model")
        self.assertEqual(anchor["config"]["epochs"], 12000)

    def test_registered_anchor_coding_returns_validated_config_without_llm_code(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        class Coding:
            def generate_candidate(self, task):
                raise AssertionError("registered anchors must not generate replacement code")

        runtime = MultiAgentRuntime(Path.cwd(), object(), Coding(), object())
        candidate = {
            "experiment_id": "anchor-1",
            "implementation_source": "registered_model",
            "model_type": "tiny_mlp",
            "config": {
                "model_type": "tiny_mlp",
                "feature_mode": "complex_mp",
                "memory_depth": 5,
                "mp_order_count": 5,
                "hidden_units": 80,
                "activation": "relu",
                "epochs": 12000,
            },
            "budget": {
                "parameter_count_max": 6000,
                "epochs_max": 12000,
                "timeout_seconds": 1800,
            },
        }

        result = runtime._coding_worker(
            {
                "run_id": "anchor-run",
                "goal": "reach -40 dB",
                "round_index": 1,
                "experiment_id": "anchor-1",
                "candidate": candidate,
                "plan": {"plan_id": "anchor-plan"},
                "prior_facts": [],
            }
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["implementation_source"], "registered_model")
        self.assertEqual(result["validation"]["estimated_parameter_count"], 5042)
        self.assertEqual(result["applied_files"], ())

    def test_registered_anchor_execution_uses_config_and_training_tools(self):
        from nonlinear_agent.execution_agent import ExecutionResult
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        class Execution:
            def __init__(self):
                self.calls = []

            async def execute(self, tool_name, arguments, cancelled=False):
                self.calls.append((tool_name, arguments))
                if tool_name == "generate_config":
                    return ExecutionResult(
                        status="completed",
                        classification="ok",
                        tool_name=tool_name,
                        output={"config_path": "runs/anchor/configs/anchor.yaml"},
                        artifacts=("runs/anchor/configs/anchor.yaml",),
                    )
                return ExecutionResult(
                    status="completed",
                    classification="ok",
                    tool_name=tool_name,
                    metrics={"nmse_db": -40.8, "parameter_count": 5042},
                    output={"metrics": {"nmse_db": -40.8, "parameter_count": 5042}},
                    artifacts=(
                        "reports/anchor/execution/metrics.json",
                        "reports/anchor/execution/psd.png",
                    ),
                )

        execution = Execution()
        runtime = MultiAgentRuntime(
            Path.cwd(),
            object(),
            object(),
            object(),
            execution_agent_factory=lambda workspace: execution,
        )
        runtime._publish_file = lambda workspace, value, run_id: value
        candidate = {
            "experiment_id": "anchor-1",
            "implementation_source": "registered_model",
            "model_type": "tiny_mlp",
            "config": {
                "model_type": "tiny_mlp",
                "feature_mode": "complex_mp",
                "memory_depth": 5,
                "mp_order_count": 5,
                "hidden_units": 80,
                "activation": "relu",
                "epochs": 12000,
                "output_dir": "reports/ignored",
            },
            "budget": {
                "parameter_count_max": 6000,
                "epochs_max": 12000,
                "timeout_seconds": 1800,
            },
        }

        result = runtime._execution_worker(
            {
                "run_id": "anchor-run",
                "goal": "reach -40 dB",
                "round_index": 1,
                "experiment_id": "anchor-1",
                "candidate": candidate,
                "plan": {"plan_id": "anchor-plan"},
                "code_result": {
                    "passed": True,
                    "implementation_source": "registered_model",
                    "worktree": str(Path.cwd()),
                },
            }
        )

        self.assertEqual([item[0] for item in execution.calls], ["generate_config", "run_training"])
        generated = execution.calls[0][1]
        self.assertEqual(generated["base_config_path"], "configs/baselines/mlp64-complexmp-direct-adam-400-lr2e3.yaml")
        self.assertEqual(generated["overrides"]["output_dir"], "reports/anchor-run-anchor-1/execution")
        self.assertEqual(result["metrics"]["nmse_db"], -40.8)
        descriptor = result["output"]["descriptor"]
        self.assertEqual(descriptor["name"], "tiny_mlp")
        self.assertEqual(
            [node["label"] for node in descriptor["nodes"]],
            ["Complex MP features", "Dense 80 + ReLU", "Complex output"],
        )

    def test_batch_report_reproduce_command_matches_actual_search_shape(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        class Router:
            def total_cost(self):
                return 0.0

        runtime = MultiAgentRuntime(Path.cwd(), Router(), object(), object())
        candidate = {
            "model_type": "tiny_mlp",
            "config": {"hidden_units": 80},
            "budget": {"parameter_count_max": 8000},
        }
        source = runtime._batch_report_source(
            {
                "run_id": "shape-1x3",
                "goal": "reach target",
                "plan": {"hypotheses": [], "candidate_experiments": []},
                "round_records": [{"round_index": 1, "outcomes": []}],
                "exploration_outcomes": [
                    {
                        "experiment_id": f"candidate-{index}",
                        "candidate": candidate,
                        "status": "completed",
                        "metrics": {"nmse_db": -30.0 - index},
                        "artifacts": [],
                    }
                    for index in range(1, 4)
                ],
                "final_evaluation": {
                    "status": "completed",
                    "source_experiment_id": "candidate-3",
                    "candidate": candidate,
                    "metrics": {"nmse_db": -33.0},
                    "artifacts": [],
                },
            }
        )

        self.assertIn("--rounds 1 --experiments-per-round 3", source["reproduce_command"])
        self.assertIn("--final-evaluation", source["reproduce_command"])

    def test_idea_plan_contract_uses_requested_experiment_count(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        class Router:
            def __init__(self):
                self.prompt = ""

            def complete(self, role, prompt):
                self.prompt = prompt
                return json.dumps(_three_candidate_plan(1))

        router = Router()
        runtime = MultiAgentRuntime(Path.cwd(), router, object(), object())

        runtime._idea_plan(
            {
                "run_id": "one-candidate-plan",
                "goal": "run one experiment",
                "round_index": 1,
                "rounds_total": 1,
                "experiments_per_round": 1,
                "available_fact_refs": [],
                "round_records": [],
            }
        )

        contract_text = router.prompt.split("\nRun request:\n", 1)[0]
        self.assertIn("Design exactly 1 distinct compact candidate", contract_text)
        self.assertIn('"experiment_id": "candidate-1"', contract_text)
        self.assertNotIn('"experiment_id": "candidate-2"', contract_text)

    def test_idea_plan_injects_bounded_context_and_protects_allowlist(self):
        from nonlinear_agent.knowledge.ingest import KnowledgeChunk
        from nonlinear_agent.knowledge.retriever import ScoredChunk
        from nonlinear_agent.memory.planner_context import PlannerContext
        from nonlinear_agent.memory.ports import MemoryItem, MemoryKind
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        plan = _three_candidate_plan(1)
        for candidate in plan["candidate_experiments"]:
            candidate["citation"] = "knowledge:prior-001"
        plan["hypotheses"][0]["citation"] = "memory:memory-001"
        plan["_planner_context"] = {"allowed_citation_ids": ["forged"]}

        class ContextBuilder:
            def __init__(self):
                self.calls = []

            def build(self, query, namespace, top_k=3):
                self.calls.append((query, namespace, top_k))
                chunk = KnowledgeChunk(
                    chunk_id="prior-001",
                    source_path="docs/knowledge/nonlinear-modeling/priors.md",
                    content_hash="abc123",
                    version="main",
                    created_at=1.0,
                    text="LUT spline candidates can exploit a compact physical prior.",
                    citation="priors.md#LUT spline",
                )
                memory = MemoryItem(
                    memory_id="memory-001",
                    kind=MemoryKind.EPISODIC,
                    namespace=("nonlinear-modeling", "dataset-42", "mixed"),
                    fact="A verified compact candidate reached -37 dB.",
                    evidence_refs=("artifact:metrics.json",),
                    metrics={"nmse_db": -37.0},
                    confidence=0.9,
                )
                return PlannerContext(
                    knowledge=(ScoredChunk(chunk=chunk, score=0.82),),
                    memory=(memory,),
                )

        class Router:
            def __init__(self):
                self.prompt = ""

            def complete(self, role, prompt):
                self.prompt = prompt
                return json.dumps(plan)

        builder = ContextBuilder()
        router = Router()
        runtime = MultiAgentRuntime(
            Path.cwd(),
            router,
            object(),
            object(),
            planner_context_builder=builder,
            planner_context_enabled=True,
            planner_namespace=("nonlinear-modeling", "dataset-42", "mixed"),
            planner_context_top_k=2,
        )

        result = runtime._idea_plan(
            {
                "run_id": "context-plan",
                "goal": "design a compact nonlinear model",
                "round_index": 1,
                "rounds_total": 3,
                "experiments_per_round": 3,
                "available_fact_refs": [],
                "round_records": [],
            }
        )

        self.assertEqual(builder.calls[0][1], ("nonlinear-modeling", "dataset-42", "mixed"))
        self.assertEqual(builder.calls[0][2], 2)
        self.assertIn("knowledge:prior-001", router.prompt)
        self.assertIn("memory:memory-001", router.prompt)
        self.assertNotIn("forged", result["_planner_context"]["allowed_citation_ids"])
        self.assertEqual(
            set(result["_planner_context"]["allowed_citation_ids"]),
            {"knowledge:prior-001", "memory:memory-001"},
        )

    def test_idea_plan_injects_budget_filtered_historical_priors_in_round_one(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        plan = _three_candidate_plan(1)
        prior_id = "prior:tiny-mem20-h96"
        for candidate in plan["candidate_experiments"]:
            candidate["citation"] = prior_id
        plan["hypotheses"][0]["citation"] = prior_id

        class Router:
            def __init__(self):
                self.prompt = ""

            def complete(self, role, prompt):
                self.prompt = prompt
                return json.dumps(plan)

        router = Router()
        runtime = MultiAgentRuntime(
            Path.cwd(),
            router,
            object(),
            object(),
            historical_priors=[
                {
                    "id": "tiny-mem20-h96",
                    "known_nmse_db": -42.2643,
                    "parameter_count": 12386,
                    "config": {"model_type": "tiny_mlp", "hidden_units": 96},
                    "source": "reports/verified/metrics.json",
                }
            ],
        )

        result = runtime._idea_plan(
            {
                "run_id": "prior-plan",
                "goal": "reach -41 dB",
                "round_index": 1,
                "rounds_total": 1,
                "experiments_per_round": 3,
                "available_fact_refs": [],
                "round_records": [],
            }
        )

        self.assertIn(prior_id, router.prompt)
        self.assertIn("-42.2643", router.prompt)
        self.assertIn(prior_id, result["_planner_context"]["allowed_citation_ids"])
        self.assertEqual(result["_planner_context"]["evidence"][0]["kind"], "prior")

    def test_execution_writes_verified_result_to_typed_memory(self):
        from nonlinear_agent.execution_agent import ExecutionResult
        from nonlinear_agent.memory.ports import MemoryKind
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        class Backend:
            def __init__(self):
                self.items = []

            def write(self, item):
                self.items.append(item)
                return item.memory_id

        class Execution:
            async def execute(self, tool_name, arguments, cancelled=False):
                return ExecutionResult(
                    status="completed",
                    classification="ok",
                    tool_name=tool_name,
                    metrics={"nmse_db": -36.5, "parameter_count": 128},
                    artifacts=("reports/memory-run/execution/metrics.json",),
                )

        backend = Backend()
        runtime = MultiAgentRuntime(
            Path.cwd(),
            object(),
            object(),
            object(),
            execution_agent_factory=lambda workspace: Execution(),
            memory_backend=backend,
            planner_namespace=("nonlinear-modeling", "dataset-42", "mixed"),
        )
        runtime._publish_file = lambda *args: "reports/memory-run/evidence/metrics.json"

        runtime._execution_worker(
            {
                "run_id": "memory-run",
                "goal": "improve NMSE",
                "round_index": 1,
                "experiment_id": "candidate-1",
                "candidate": {
                    "experiment_id": "candidate-1",
                    "model_type": "CompactLUT",
                    "config": {"knots": 16},
                    "budget": {"parameter_count_max": 4000, "timeout_seconds": 30},
                },
                "plan": {"plan_id": "plan-memory"},
                "code_result": {
                    "worktree": str(Path.cwd()),
                    "manifest_path": "models/candidates/compact_lut/manifest.json",
                },
            }
        )

        self.assertEqual(len(backend.items), 1)
        item = backend.items[0]
        self.assertEqual(item.kind, MemoryKind.EPISODIC)
        self.assertEqual(item.namespace, ("nonlinear-modeling", "dataset-42", "mixed"))
        self.assertEqual(item.metrics["nmse_db"], -36.5)
        self.assertIn("CompactLUT", item.fact)
        self.assertEqual(item.created_by_role, "execution")

    def test_empty_retrieval_does_not_create_an_impossible_citation_allowlist(self):
        from nonlinear_agent.memory.planner_context import PlannerContext
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        class EmptyContextBuilder:
            def build(self, query, namespace, top_k=3):
                return PlannerContext()

        runtime = MultiAgentRuntime(
            Path.cwd(),
            object(),
            object(),
            object(),
            planner_context_builder=EmptyContextBuilder(),
            planner_context_enabled=True,
        )

        context = runtime._build_planner_context(
            {"goal": "unmatched query", "round_index": 1, "round_records": []}
        )

        self.assertTrue(context["requested"])
        self.assertFalse(context["enabled"])
        self.assertEqual(context["allowed_citation_ids"], [])

    def test_writing_worker_refreshes_cost_after_the_writing_model_call(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime
        from tests.test_reporting_tool import _task_source

        class Router:
            cost = 0.1

            def total_cost(self):
                return self.cost

        class Writer:
            def __init__(self, router):
                self.router = router

            def write(self, bundle):
                self.router.cost = 0.25

                class Narrative:
                    def to_dict(self):
                        return {"schema_version": 1, "task_id": bundle.task_id, "sections": {}}

                return Narrative()

        captured = []
        router = Router()
        runtime = MultiAgentRuntime(
            Path.cwd(),
            router,
            object(),
            Writer(router),
            report_writer=lambda **kwargs: captured.append(kwargs["task_source"]) or {},
        )
        runtime._report_source = lambda request: _task_source()

        runtime._writing_worker({"run_id": "cost-refresh"})

        self.assertEqual(captured[0]["cost_usd"], 0.25)

    def test_idea_plan_repairs_one_non_json_response_with_failure_fact(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        valid = _three_candidate_plan(1)

        class Router:
            def __init__(self):
                self.prompts = []
                self.responses = ["I need more time to think.", json.dumps(valid)]

            def complete(self, role, prompt):
                self.prompts.append((role, prompt))
                return self.responses.pop(0)

        router = Router()
        runtime = MultiAgentRuntime(Path.cwd(), router, object(), object())

        result = runtime._idea_plan(
            {
                "run_id": "repair-plan",
                "goal": "find a compact model",
                "round_index": 1,
                "rounds_total": 3,
                "experiments_per_round": 3,
                "available_fact_refs": [],
                "round_records": [],
            }
        )

        self.assertEqual(result["plan_id"], valid["plan_id"])
        self.assertEqual(len(router.prompts), 2)
        self.assertIn("Previous response failed validation", router.prompts[1][1])
        self.assertIn("must contain one JSON object", router.prompts[1][1])

    def test_runtime_prompts_for_three_candidates_and_targets_requested_experiment(self):
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime

        plan = _three_candidate_plan(2, ("fact:round-1:best:r1-exp3",))
        plan["candidate_experiments"][1]["model_type"] = "CompactSinMLP"

        class Router:
            def __init__(self):
                self.prompts = []

            def complete(self, role, prompt):
                self.prompts.append((role, prompt))
                return "```json\n" + json.dumps(plan) + "\n```"

            def total_cost(self):
                return 0.0

        @dataclass(frozen=True)
        class CodingResult:
            passed: bool = True
            task_id: str = ""
            candidate_name: str = ""
            worktree: str = ""
            manifest_path: str = "models/candidates/model/manifest.json"
            applied_files: tuple[str, ...] = ()
            attempt_count: int = 1
            failure_facts: tuple[str, ...] = ()
            validation: dict = None
            metrics: dict = None
            artifacts: tuple[str, ...] = ()
            trace_path: str = ""

        class Coding:
            def __init__(self):
                self.tasks = []
                self.max_repairs = []

            def generate_candidate(self, task, max_repairs=2):
                self.tasks.append(task)
                self.max_repairs.append(max_repairs)
                return CodingResult(
                    task_id=task.task_id,
                    candidate_name=task.candidate_name,
                )

        router = Router()
        coding = Coding()
        runtime = MultiAgentRuntime(
            repo_root=Path.cwd(),
            model_router=router,
            coding_agent=coding,
            writing_agent=object(),
            coding_max_repairs=4,
        )

        planned = runtime._idea_plan(
            {
                "run_id": "run-3x3",
                "goal": "improve compact nonlinear model",
                "round_index": 2,
                "rounds_total": 3,
                "experiments_per_round": 3,
                "available_fact_refs": ["fact:round-1:best:r1-exp3"],
                "round_records": [],
            }
        )
        candidate = planned["candidate_experiments"][1]
        result = runtime._coding_worker(
            {
                "run_id": "run-3x3",
                "goal": "improve compact nonlinear model",
                "round_index": 2,
                "experiment_id": candidate["experiment_id"],
                "candidate": candidate,
                "plan": planned,
                "prior_facts": [
                    {
                        "experiment_id": "r1-candidate-1",
                        "status": "failed",
                        "metrics": {},
                        "failure_facts": [
                            "TypeError: ArchitectureNode got unexpected keyword id"
                        ],
                    }
                ],
            }
        )

        prompt = router.prompts[0][1]
        self.assertIn("exactly 3 distinct compact candidates", prompt)
        self.assertIn('"experiment_id": "candidate-3"', prompt)
        self.assertIn("available_fact_refs", prompt)
        self.assertEqual(coding.tasks[0].candidate_name, "compact_sin_mlp")
        self.assertIn("candidate-2", coding.tasks[0].task_id)
        self.assertEqual(result["candidate_name"], "compact_sin_mlp")
        self.assertEqual(coding.max_repairs, [4])
        self.assertIn("unexpected keyword id", coding.tasks[0].objective)
        self.assertIn("adapt architecture", coding.tasks[0].objective)
        self.assertTrue(
            any("unexpected keyword id" in item for item in coding.tasks[0].constraints)
        )

    def test_existing_components_are_adapted_into_one_evidence_chain(self):
        from nonlinear_agent.model_router import ModelRouter
        from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime
        from nonlinear_agent.supervisor_graph import build_multi_agent_graph, run_multi_agent_graph

        class Client:
            provider = "fake"
            model = "idea-model"
            total_prompt_tokens = 0
            total_completion_tokens = 0

            def __init__(self):
                self.prompts = []

            def complete(self, prompt: str) -> str:
                self.prompts.append(prompt)
                self.total_prompt_tokens += 20
                self.total_completion_tokens += 10
                return json.dumps(_plan())

        client = Client()
        router = ModelRouter(
            {"idea_plan": {"provider": "fake", "model": "idea-model"}},
            client_factory=lambda role, config: client,
        )

        @dataclass(frozen=True)
        class CodingResult:
            passed: bool = True
            task_id: str = "run-001"
            candidate_name: str = "adaptive_wavelet_lut"
            worktree: str = ""
            manifest_path: str = "models/candidates/adaptive_wavelet_lut/manifest.json"
            applied_files: tuple[str, ...] = ("models/candidates/adaptive_wavelet_lut/plugin.py",)
            attempt_count: int = 1
            failure_facts: tuple[str, ...] = ()
            validation: dict = None
            metrics: dict = None
            artifacts: tuple[str, ...] = ()
            trace_path: str = "runs/coding-agent/run-001/coding-trace.json"

        class Coding:
            def __init__(self, root: Path):
                self.root = root
                self.tasks = []

            def generate_candidate(self, task, max_repairs=2):
                self.tasks.append(task)
                return CodingResult(
                    worktree=str(self.root),
                    validation={"descriptor": descriptor, "parameter_count": 128},
                    metrics={},
                )

        class Execution:
            async def execute(self, tool_name, arguments, cancelled=False):
                from nonlinear_agent.execution_agent import ExecutionResult

                self.tool_name = tool_name
                self.arguments = arguments
                return ExecutionResult(
                    status="completed",
                    classification="ok",
                    tool_name=tool_name,
                    metrics={"nmse_db": -37.5, "parameter_count": 128},
                    output={"descriptor": descriptor},
                    artifacts=("reports/run-001/execution/psd.png",),
                )

        class Writer:
            def __init__(self):
                self.bundle = None

            def write(self, bundle):
                self.bundle = bundle
                class Narrative:
                    def to_dict(self):
                        return {"schema_version": 1, "task_id": bundle.task_id, "sections": {}}

                return Narrative()

        descriptor = {
            "name": "adaptive_wavelet_lut",
            "version": "1.0.0",
            "training_mode": "custom",
            "config_schema": {"type": "object", "properties": {}},
            "nodes": [{"node_id": "lut", "label": "Wavelet LUT", "operation": "lookup"}],
            "edges": [],
        }

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            coding_root = root / "coding-worktree"
            psd = coding_root / "reports" / "run-001" / "execution" / "psd.png"
            psd.parent.mkdir(parents=True)
            psd.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            coding = Coding(coding_root)
            execution = Execution()
            writer = Writer()
            report_sources = []

            def report_writer(**kwargs):
                report_sources.append(kwargs["task_source"])
                self.assertEqual(Path(kwargs["workspace"]), root.resolve())
                published_psd = root / kwargs["task_source"]["executions"][0]["psd_path"]
                self.assertTrue(published_psd.is_file())
                return {
                    "html_path": "reports/run-001/report.html",
                    "pdf_path": "reports/run-001/report.pdf",
                    "artifacts": ["reports/run-001/report.pdf"],
                }

            runtime = MultiAgentRuntime(
                repo_root=root,
                model_router=router,
                coding_agent=coding,
                writing_agent=writer,
                execution_agent_factory=lambda workspace: execution,
                report_writer=report_writer,
                nmse_threshold_db=-35.0,
            )
            graph = build_multi_agent_graph(
                runtime.workers(), model_router=router
            )
            result = run_multi_agent_graph(
                graph,
                goal="design an unseen compact nonlinear model",
                run_id="run-001",
            )

        self.assertEqual(result["status"], "completed")
        self.assertIn("candidate_experiments", client.prompts[0])
        self.assertIn("required_code_changes", client.prompts[0])
        self.assertIn("failure_facts", client.prompts[0])
        self.assertEqual(coding.tasks[0].candidate_name, "adaptive_wavelet_lut")
        self.assertEqual(execution.tool_name, "run_candidate_model")
        self.assertEqual(
            report_sources[0]["goal"], "design an unseen compact nonlinear model"
        )
        self.assertEqual(report_sources[0]["executions"][0]["nmse_db"], -37.5)
        self.assertEqual(
            report_sources[0]["executions"][0]["model_descriptor"]["name"],
            "adaptive_wavelet_lut",
        )
        self.assertEqual(writer.bundle.architecture.name, "adaptive_wavelet_lut")
        self.assertEqual(result["terminal"]["pdf_path"], "reports/run-001/report.pdf")


if __name__ == "__main__":
    unittest.main()

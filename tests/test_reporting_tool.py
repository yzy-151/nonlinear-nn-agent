"""TDD tests: nnagent produces task reports through the write_task_report tool."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from nonlinear_agent.execution_agent import ExecutionAgent
from nonlinear_agent.tools import ToolRegistry


def _task_source(root: Path | None = None) -> dict:
    source = {
        "task_id": "tool-task-001",
        "goal": "在 4000 参数预算内找到 NMSE <= -35 dB 的非线性模型",
        "constraints": {"parameter_count_max": 4000, "nmse_threshold_db": -35.0},
        "citations": ["docs/handoff/llm-continuation-plan.md#8. DeepSeek self-correction case"],
        "plan": {
            "hypotheses": [{"假设": "增大 memory depth 提升拟合能力", "依据": "历史实验显示有效"}],
            "candidate_experiments": [
                {"model_type": "tiny_mlp", "params_estimate": 1200, "停止条件": "NMSE<=-35"}
            ],
            "experiment_dag": {"nodes": ["exp_001"], "edges": []},
        },
        "code_changes": [
            {"file": "src/nonlinear_agent/domains/nonlinear_modeling.py", "change": "新增 silu 激活"}
        ],
        "executions": [
            {
                "run_id": "exp_019",
                "model_type": "complex_lstsq",
                "nmse_db": -36.03,
                "parameter_count": 202,
                "baseline_nmse_db": -21.83,
                "psd_path": None,
                "target_hit": True,
                "cost_usd": 0.031,
                "hidden_units": 64,
                "memory_depth": 24,
            },
            {
                "run_id": "exp016",
                "model_type": "adaptive_wavelet_lut",
                "nmse_db": -37.49,
                "parameter_count": 3980,
                "baseline_nmse_db": -21.83,
                "psd_path": None,
                "target_hit": True,
                "cost_usd": 0.042,
                "hidden_units": 64,
                "memory_depth": 220,
                "model_descriptor": {
                    "name": "adaptive_wavelet_lut",
                    "version": "1.0.0",
                    "training_mode": "custom",
                    "config_schema": {"type": "object", "properties": {}},
                    "nodes": [
                        {"node_id": "input", "label": "Complex Input", "operation": "input", "details": {"shape": "2 x M"}},
                        {"node_id": "memory", "label": "Memory Bank", "operation": "delay_embedding", "details": {"depth": 16}},
                        {"node_id": "lut", "label": "Adaptive Wavelet LUT", "operation": "wavelet_lookup", "details": {"knots": 16}},
                        {"node_id": "output", "label": "Linear Readout", "operation": "linear", "details": {"channels": 2}},
                    ],
                    "edges": [
                        {"source": "input", "target": "memory", "label": "I/Q"},
                        {"source": "memory", "target": "lut", "label": "features"},
                        {"source": "lut", "target": "output", "label": "basis"},
                    ],
                },
            },
            {
                "run_id": "exp_020",
                "model_type": "tiny_mlp",
                "nmse_db": -29.50,
                "parameter_count": 900,
                "baseline_nmse_db": -21.83,
                "psd_path": None,
                "target_hit": False,
                "cost_usd": 0.028,
                "hidden_units": 32,
                "memory_depth": 8,
            },
        ],
        "ablations": [
            {"名称": "llm_direct", "best_nmse_db": -33.59},
            {"名称": "llm_program_reflection", "best_nmse_db": -37.87},
        ],
        "failure_cases": [
            {"id": "exp_021", "状态": "rejected", "错误": "非法字段 spline_range"}
        ],
        "cost_usd": 0.101,
        "trace_refs": ["traces/tool-task-001.jsonl"],
        "reproduce_command": "python agent.py run --provider deepseek",
        "limits": "训练预算 1 小时；仅非线性建模域",
    }
    if root is not None:
        psd = root / "real-psd.png"
        _png(psd)
        source["executions"][1]["psd_path"] = str(psd)
    return source


def _png(path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(4, 2))
    ax.plot([0, 1], [-80, -100])
    fig.savefig(path, dpi=72)
    plt.close(fig)


def _three_round_task_source(root: Path) -> dict:
    source = _task_source(root)
    descriptor = dict(source["executions"][1]["model_descriptor"])
    descriptor["name"] = "final_unseen_model"
    executions = []
    round_records = []
    for round_index in range(1, 4):
        outcomes = []
        for experiment_index in range(1, 4):
            run_id = f"r{round_index}-exp{experiment_index}"
            nmse = -30.0 - round_index - experiment_index
            if run_id == "r3-exp3":
                nmse = -39.0
            execution = {
                "run_id": run_id,
                "round_index": round_index,
                "model_type": f"unseen_model_{round_index}_{experiment_index}",
                "nmse_db": nmse,
                "parameter_count": 1000 + round_index * 100 + experiment_index,
                "baseline_nmse_db": -21.83,
                "psd_path": None,
                "target_hit": nmse <= -35.0,
                "config": {"optimizer": "adam", "learning_rate": 0.001},
            }
            executions.append(execution)
            outcomes.append(
                {
                    "experiment_id": run_id,
                    "candidate_name": execution["model_type"],
                    "status": "completed",
                    "metrics": {
                        "nmse_db": nmse,
                        "parameter_count": execution["parameter_count"],
                    },
                    "evidence_refs": [f"metric:{run_id}"],
                }
            )
        round_records.append(
            {
                "round_index": round_index,
                "incoming_fact_refs": (
                    [] if round_index == 1 else [f"fact:round-{round_index - 1}:best"]
                ),
                "hypothesis": f"round {round_index} hypothesis",
                "decision_rationale": f"round {round_index} evidence-driven rationale",
                "experiment_ids": [item["experiment_id"] for item in outcomes],
                "outcomes": outcomes,
                "extracted_facts": [f"fact:round-{round_index}:best"],
                "next_round_intent": (
                    "refine from measured error" if round_index < 3 else "final evaluation"
                ),
            }
        )
    final_psd = root / "final-real-psd.png"
    _png(final_psd)
    source["executions"] = executions
    source["round_records"] = round_records
    source["final_evaluation"] = {
        "run_id": "r3-exp3-final",
        "source_experiment_id": "r3-exp3",
        "evaluation_kind": "final",
        "status": "completed",
        "model_type": "final_unseen_model",
        "nmse_db": -38.5,
        "parameter_count": 1303,
        "baseline_nmse_db": -21.83,
        "psd_path": str(final_psd),
        "target_hit": True,
        "model_descriptor": descriptor,
        "config": {
            "optimizer": "adam",
            "learning_rate": 0.001,
            "seed": 2026,
            "dataset_split": "fixed-test",
        },
    }
    return source


def _analysis() -> dict[str, str]:
    return {
        "improvement": (
            "从基线 complex_lstsq（-21.8 dB）出发，增大 memory depth 至 24/220 "
            "后 NMSE 达到 -36.0 / -37.5 dB，相对基线提升约 15 dB。"
        ),
        "why_effective": (
            "memory depth 增加让模型捕获更长的非线性记忆；hidden_units 与激活函数"
            "选择影响表达能力，silu 在保持稳定训练的同时提升拟合精度。"
        ),
        "experience": (
            "先验注入 + 邻域搜索让 LLM 从已知最优区域起步；"
            "Guard 拦截非法参数避免无效训练；下次可优先探索更大 memory depth 与更小参数量组合。"
        ),
    }


class TestWriteTaskReportTool(unittest.TestCase):
    def test_architecture_graph_uses_readable_report_font_sizes(self):
        from nonlinear_agent.reporting.figures import (
            ARCH_EDGE_FONT_SIZE,
            ARCH_NODE_FONT_SIZE,
        )

        self.assertGreaterEqual(ARCH_NODE_FONT_SIZE, 14.0)
        self.assertGreaterEqual(ARCH_EDGE_FONT_SIZE, 11.0)

    def test_three_round_report_keeps_all_runs_but_uses_only_final_psd_and_architecture(self):
        from nonlinear_agent.reporting.tool import write_task_report_tool

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = write_task_report_tool(
                workspace=root,
                task_source=_three_round_task_source(root),
                output_dir="reports/three-round",
            )
            html = (root / result["html_path"]).read_text(encoding="utf-8")

            self.assertEqual(html.count('class="round-card"'), 3)
            self.assertEqual(html.count("figures/psd.png"), 1)
            self.assertIn("final_unseen_model", html)
            self.assertIn("r3-exp3-final", html)
            for round_index in range(1, 4):
                for experiment_index in range(1, 4):
                    self.assertIn(f"r{round_index}-exp{experiment_index}", html)

    def test_final_evaluation_must_supply_the_report_psd(self):
        from nonlinear_agent.reporting.pdf_renderer import RenderError
        from nonlinear_agent.reporting.tool import write_task_report_tool

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _three_round_task_source(root)
            source["final_evaluation"]["psd_path"] = None
            with self.assertRaisesRegex(RenderError, "final evaluation.*PSD"):
                write_task_report_tool(
                    workspace=root,
                    task_source=source,
                    output_dir="reports/missing-final-psd",
                )

    def _agent(self) -> ExecutionAgent:
        from nonlinear_agent.experiment_tools import build_experiment_tool_registry

        return ExecutionAgent(build_experiment_tool_registry("."))

    def test_agent_generates_report_via_tool(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            agent = ExecutionAgent(
                ToolRegistry()  # placeholder replaced below by project registry
            )
            from nonlinear_agent.experiment_tools import build_experiment_tool_registry

            agent = ExecutionAgent(build_experiment_tool_registry(root))
            result = asyncio.run(
                agent.execute(
                    "write_task_report",
                    {
                        "task_source": _task_source(root),
                        "output_dir": "reports/tool-test",
                        "analysis": _analysis(),
                    },
                )
            )
            self.assertEqual(result.status, "completed", result.error)
            self.assertEqual(agent.audit_shell_calls(), 0)
            pdf_rel = result.output.get("pdf_path")
            self.assertTrue(pdf_rel, "tool must return pdf_path")
            self.assertTrue((root / pdf_rel).exists())
            html_rel = result.output.get("html_path")
            self.assertTrue((root / html_rel).exists())

    def test_html_contains_analysis_and_data_sections(self):
        from nonlinear_agent.experiment_tools import build_experiment_tool_registry

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            agent = ExecutionAgent(build_experiment_tool_registry(root))
            result = asyncio.run(
                agent.execute(
                    "write_task_report",
                    {
                        "task_source": _task_source(root),
                        "output_dir": "reports/tool-test",
                        "analysis": _analysis(),
                    },
                )
            )
            html_path = root / result.output["html_path"]
            content = html_path.read_text(encoding="utf-8")
            for section in (
                "执行摘要",
                "实际模型架构",
                "性能证据",
                "失败、反思与经验",
                "代码、Trace 与复现",
                "适用边界",
            ):
                self.assertIn(section, content)
            self.assertIn("模型描述符给出的实际处理节点", content)
            self.assertIn("architecture.png", content)
            self.assertIn("psd.png", content)
            self.assertIn("improvement.png", content)
            self.assertIn("-37.49", content)
            self.assertIn("adaptive_wavelet_lut", content)
            self.assertIn("Adaptive Wavelet LUT", content)

    def test_pdf_is_generated_with_chinese(self):
        from nonlinear_agent.experiment_tools import build_experiment_tool_registry

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            agent = ExecutionAgent(build_experiment_tool_registry(root))
            result = asyncio.run(
                agent.execute(
                    "write_task_report",
                    {
                        "task_source": _task_source(root),
                        "output_dir": "reports/tool-test",
                        "analysis": _analysis(),
                    },
                )
            )
            pdf_path = root / result.output["pdf_path"]
            self.assertGreater(pdf_path.stat().st_size, 1000)
            import fitz

            doc = fitz.open(str(pdf_path))
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            self.assertIn("任务报告", text)
            self.assertIn("-36.03", text)

    def test_missing_real_psd_is_rejected_instead_of_fabricated(self):
        from nonlinear_agent.experiment_tools import build_experiment_tool_registry

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            agent = ExecutionAgent(build_experiment_tool_registry(root))
            result = asyncio.run(
                agent.execute(
                    "write_task_report",
                    {
                        "task_source": _task_source(),
                        "output_dir": "reports/tool-test",
                    },
                )
            )
            self.assertEqual(result.status, "failed")
            self.assertIn("real PSD", result.error)

    def test_empty_executions_yields_failed_tool_call(self):
        from nonlinear_agent.experiment_tools import build_experiment_tool_registry

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            agent = ExecutionAgent(build_experiment_tool_registry(root))
            source = _task_source(root)
            source["executions"] = []
            result = asyncio.run(
                agent.execute(
                    "write_task_report",
                    {"task_source": source, "output_dir": "reports/tool-test"},
                )
            )
            self.assertEqual(result.status, "failed")
            self.assertIn("executions is empty", result.error)

    def test_tool_accepts_cited_narrative_and_rejects_hallucinated_number(self):
        from nonlinear_agent.experiment_tools import build_experiment_tool_registry
        from nonlinear_agent.writing_agent import NarrativeSpec
        from tests.test_writing_agent import _narrative_response

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            agent = ExecutionAgent(build_experiment_tool_registry(root))
            valid = NarrativeSpec.from_json(_narrative_response()).to_dict()
            result = asyncio.run(
                agent.execute(
                    "write_task_report",
                    {
                        "task_source": _task_source(root),
                        "output_dir": "reports/cited",
                        "narrative": valid,
                    },
                )
            )
            self.assertEqual(result.status, "completed", result.error)
            html = (root / result.output["html_path"]).read_text(encoding="utf-8")
            self.assertIn("architecture:adaptive_wavelet_lut", html)

            invalid = NarrativeSpec.from_json(
                _narrative_response(nmse=-99.0)
            ).to_dict()
            rejected = asyncio.run(
                agent.execute(
                    "write_task_report",
                    {
                        "task_source": _task_source(root),
                        "output_dir": "reports/rejected",
                        "narrative": invalid,
                    },
                )
            )
            self.assertEqual(rejected.status, "failed")
            self.assertIn("unsupported number", rejected.error)

    def test_lstsq_architecture_does_not_claim_a_hidden_activation_layer(self):
        from nonlinear_agent.reporting.figures import architecture_stage_labels

        labels = architecture_stage_labels(
            "complex_lstsq",
            {"memory_depth": 24, "mp_order_count": 12, "activation": "silu"},
        )
        joined = " ".join(labels)
        self.assertIn("最小二乘", joined)
        self.assertNotIn("silu", joined)
        self.assertNotIn("隐藏层", joined)


if __name__ == "__main__":
    unittest.main()

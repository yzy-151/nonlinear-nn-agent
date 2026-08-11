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
                "model_type": "complex_lstsq",
                "nmse_db": -37.49,
                "parameter_count": 3980,
                "baseline_nmse_db": -21.83,
                "psd_path": None,
                "target_hit": True,
                "cost_usd": 0.042,
                "hidden_units": 64,
                "memory_depth": 220,
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
                "网络原理框图",
                "改进过程与效果",
                "为什么有效",
                "实验结果",
                "数据化总结",
                "经验总结",
                "消融",
                "失败案例",
                "复现",
            ):
                self.assertIn(section, content)
            self.assertIn("memory depth 增加", content)  # agent analysis rendered
            self.assertIn("architecture.png", content)
            self.assertIn("psd.png", content)
            self.assertIn("improvement.png", content)
            self.assertIn("-37.49", content)

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

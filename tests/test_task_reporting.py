"""TDD tests for v3.9.x task-level Chinese reporting with tables/images/marks."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


def _task_source() -> dict:
    return {
        "task_id": "task-001",
        "goal": "在 4000 参数预算内找到 NMSE <= -35 dB 的非线性模型",
        "constraints": {"parameter_count_max": 4000, "nmse_threshold_db": -35.0},
        "citations": ["docs/handoff/llm-continuation-plan.md#8. DeepSeek self-correction case"],
        "plan": {
            "hypotheses": [
                {"假设": "增大 memory depth 提升拟合能力", "依据": "历史实验显示 memory 扩展有效"}
            ],
            "candidate_experiments": [
                {"model_type": "tiny_mlp", "params_estimate": 1200, "停止条件": "NMSE<=-35"}
            ],
            "experiment_dag": {"nodes": ["exp_001"], "edges": []},
        },
        "code_changes": [
            {"file": "src/nonlinear_agent/domains/nonlinear_modeling.py", "change": "新增 silu 激活选项"}
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
        "trace_refs": ["traces/task-001.jsonl"],
        "reproduce_command": "python agent.py run --provider deepseek",
        "limits": "训练预算 1 小时；仅非线性建模域",
    }


def _png(path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(4, 2))
    ax.plot([0, 1], [0, 1])
    fig.savefig(path, dpi=72)
    plt.close(fig)


class TestTaskReportBuilder(unittest.TestCase):
    def test_builder_extracts_task_level_data(self):
        from nonlinear_agent.reporting.task_report_spec import TaskReportBuilder

        spec = TaskReportBuilder().build(_task_source())
        self.assertEqual(spec.task_id, "task-001")
        self.assertEqual(len(spec.executions), 3)
        self.assertEqual(spec.cost_usd, 0.101)
        self.assertEqual(spec.executions[2].target_hit, False)
        self.assertEqual(spec.best().run_id, "exp016")


class TestTaskFidelity(unittest.TestCase):
    def test_matching_task_numbers_pass(self):
        from nonlinear_agent.reporting.fidelity import TaskFidelityChecker
        from nonlinear_agent.reporting.task_report_spec import TaskReportBuilder

        source = _task_source()
        spec = TaskReportBuilder().build(source)
        self.assertEqual(TaskFidelityChecker().check(spec, source), [])

    def test_tampered_run_number_detected(self):
        from nonlinear_agent.reporting.fidelity import TaskFidelityChecker
        from nonlinear_agent.reporting.task_report_spec import TaskReportBuilder

        source = _task_source()
        spec = TaskReportBuilder().build(source)
        runs = [
            r if r.run_id != "exp_019" else r.__class__(**{**r.__dict__, "nmse_db": -99.0})
            for r in spec.executions
        ]
        spec = spec.__class__(**{**spec.__dict__, "executions": tuple(runs)})
        mismatches = TaskFidelityChecker().check(spec, source)
        self.assertTrue(any("exp_019" in m and "nmse" in m for m in mismatches))


class TestTaskMarkdown(unittest.TestCase):
    def test_markdown_is_chinese_with_tables_and_marks(self):
        from nonlinear_agent.reporting.markdown_renderer import render_task_markdown
        from nonlinear_agent.reporting.task_report_spec import TaskReportBuilder

        md = render_task_markdown(TaskReportBuilder().build(_task_source()))
        self.assertIn("任务报告", md)
        self.assertIn("目标", md)
        self.assertIn("计划", md)
        self.assertIn("代码变更", md)
        self.assertIn("实验结果", md)
        self.assertIn("消融", md)
        self.assertIn("失败案例", md)
        self.assertIn("成本", md)
        self.assertIn("复现", md)
        self.assertIn("限制", md)
        # 表格 + 达标标注 + 最优标注
        self.assertIn("|", md)
        self.assertIn("✅", md)
        self.assertIn("⭐", md)
        self.assertIn("-36.03", md)


class TestTaskPDF(unittest.TestCase):
    def test_pdf_is_chinese_with_table_image_and_marks(self):
        from nonlinear_agent.reporting.pdf_renderer import render_task_pdf
        from nonlinear_agent.reporting.task_report_spec import TaskReportBuilder

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _task_source()
            psd1 = root / "psd1.png"
            _png(psd1)
            source["executions"][0]["psd_path"] = str(psd1)
            pdf_path = render_task_pdf(
                TaskReportBuilder().build(source),
                output_dir=root,
                figures={
                    "architecture": str(psd1),
                    "psd": str(psd1),
                    "improvement": str(psd1),
                },
            )
            self.assertTrue(pdf_path.exists())
            self.assertGreater(pdf_path.stat().st_size, 1000)
            import fitz

            doc = fitz.open(str(pdf_path))
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            self.assertIn("任务报告", text)
            self.assertIn("实验结果", text)
            self.assertIn("-36.03", text)

    def test_pdf_all_psd_missing_yields_render_error(self):
        from nonlinear_agent.reporting.pdf_renderer import (
            RenderError,
            render_task_pdf,
        )
        from nonlinear_agent.reporting.task_report_spec import TaskReportBuilder

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(RenderError) as ctx:
                render_task_pdf(
                    TaskReportBuilder().build(_task_source()), output_dir=root
                )
            self.assertTrue(any("psd" in e.lower() for e in ctx.exception.errors))


if __name__ == "__main__":
    unittest.main()

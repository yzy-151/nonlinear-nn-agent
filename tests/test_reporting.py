"""TDD tests for v3.9.0: ReportSpec, numeric fidelity, Markdown/PDF renderers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


def _source(run_id: str = "run-001", nmse: float = -36.5, params: int = 218) -> dict:
    return {
        "run_id": run_id,
        "goal": "reach -35 dB under 4000 params",
        "baseline_nmse_db": -21.8,
        "nmse_db": nmse,
        "parameter_count": params,
        "cost_usd": 0.061,
        "psd_path": None,
        "trace_refs": [f"traces/{run_id}.jsonl"],
        "reproduce_command": f"python train.py --config runs/{run_id}/config.yaml",
        "best_candidates": [
            {"model_type": "tiny_mlp", "nmse_db": nmse, "parameter_count": params}
        ],
        "failure_cases": [
            {"id": "exp001", "status": "rejected", "error": "unsupported field"}
        ],
    }


def _png(path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(4, 2))
    ax.plot([0, 1], [0, 1])
    fig.savefig(path, dpi=72)
    plt.close(fig)


class TestReportSpecBuilder(unittest.TestCase):
    def test_builder_extracts_numbers_from_source(self):
        from nonlinear_agent.reporting.report_spec import ReportSpecBuilder

        source = _source()
        spec = ReportSpecBuilder().build(source)
        self.assertEqual(spec.run_id, "run-001")
        self.assertEqual(spec.current_nmse_db, -36.5)
        self.assertEqual(spec.parameter_count, 218)
        self.assertEqual(spec.baseline_nmse_db, -21.8)


class TestFidelityChecker(unittest.TestCase):
    def test_matching_numbers_pass_with_zero_mismatch(self):
        from nonlinear_agent.reporting.fidelity import FidelityChecker
        from nonlinear_agent.reporting.report_spec import ReportSpecBuilder

        source = _source()
        spec = ReportSpecBuilder().build(source)
        mismatches = FidelityChecker().check(spec, source)
        self.assertEqual(mismatches, [])

    def test_tampered_number_is_detected(self):
        from nonlinear_agent.reporting.fidelity import FidelityChecker
        from nonlinear_agent.reporting.report_spec import ReportSpecBuilder

        source = _source(nmse=-36.5)
        spec = ReportSpecBuilder().build(source)
        # 篡改 spec 数字（模拟 renderer 写错）
        spec = spec.__class__(
            **{
                **spec.__dict__,
                "current_nmse_db": -42.0,
            }
        )
        mismatches = FidelityChecker().check(spec, source)
        self.assertTrue(any("nmse_db" in m for m in mismatches))


class TestMarkdownRenderer(unittest.TestCase):
    REQUIRED_SECTIONS = [
        "Baseline",
        "Current",
        "Best Candidates",
        "Failure Cases",
        "Cost",
        "Trace",
        "Reproduce",
    ]

    def test_markdown_contains_all_required_sections_and_numbers(self):
        from nonlinear_agent.reporting.markdown_renderer import render_markdown
        from nonlinear_agent.reporting.report_spec import ReportSpecBuilder

        source = _source()
        md = render_markdown(ReportSpecBuilder().build(source))
        for section in self.REQUIRED_SECTIONS:
            self.assertIn(section, md)
        self.assertIn("-36.5", md)
        self.assertIn("218", md)


class TestPDFRenderer(unittest.TestCase):
    def test_pdf_generates_and_contains_key_numbers(self):
        from nonlinear_agent.reporting.pdf_renderer import render_pdf
        from nonlinear_agent.reporting.report_spec import ReportSpecBuilder

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            psd = root / "psd.png"
            _png(psd)
            source = _source()
            source["psd_path"] = str(psd)
            pdf_path = render_pdf(ReportSpecBuilder().build(source), output_dir=root)
            self.assertTrue(pdf_path.exists())
            self.assertGreater(pdf_path.stat().st_size, 1000)
            import pdfplumber

            with pdfplumber.open(str(pdf_path)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            self.assertIn("-36.5", text)
            self.assertIn("218", text)

    def test_missing_psd_yields_structured_render_error(self):
        from nonlinear_agent.reporting.pdf_renderer import (
            RenderError,
            render_pdf,
        )
        from nonlinear_agent.reporting.report_spec import ReportSpecBuilder

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _source()
            with self.assertRaises(RenderError) as ctx:
                render_pdf(ReportSpecBuilder().build(source), output_dir=root)
            self.assertTrue(any("psd" in e.lower() for e in ctx.exception.errors))

    def test_three_different_runs_generate_successfully(self):
        from nonlinear_agent.reporting.pdf_renderer import render_pdf
        from nonlinear_agent.reporting.report_spec import ReportSpecBuilder

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for i, run_id in enumerate(["run-a", "run-b", "run-c"]):
                psd = root / f"psd-{i}.png"
                _png(psd)
                source = _source(run_id=run_id, nmse=-30.0 - i, params=100 + i)
                source["psd_path"] = str(psd)
                out = root / f"report-{i}"
                out.mkdir()
                pdf_path = render_pdf(
                    ReportSpecBuilder().build(source), output_dir=out
                )
                self.assertTrue(pdf_path.exists())
                self.assertGreater(pdf_path.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()

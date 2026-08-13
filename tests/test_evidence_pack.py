import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.evidence_pack import (
    build_evidence_summary,
    merge_agent_benchmark_reports,
    write_evidence_pack,
)


class EvidencePackTest(unittest.TestCase):
    def _agent_report(self, mode, passed):
        rows = []
        for index, value in enumerate(passed):
            rows.append({
                "case_id": f"case-{index}", "attempt": 1,
                "passed": value, "category": "recovery",
                "total_prompt_tokens": 10, "total_completion_tokens": 5,
            })
        return {
            "evaluation_mode": mode,
            "task_count": len(rows), "attempt_count": len(rows),
            "pass_at_1": sum(passed) / len(passed), "results": rows,
        }

    def test_summary_keeps_scripted_and_real_llm_claims_separate(self):
        summary = build_evidence_summary(
            scripted=self._agent_report("scripted_fixture", [True, True]),
            online=self._agent_report("real_llm_fault_fixture", [True, False]),
            search_summary={"per_method": {}},
            stress={"pass": True, "duplicate_execution_rate": 0.0},
        )

        self.assertEqual(summary["agent_behavior"]["scripted"]["pass_at_1"], 1.0)
        self.assertEqual(summary["agent_behavior"]["online"]["pass_at_1"], 0.5)
        self.assertNotEqual(
            summary["agent_behavior"]["scripted"]["claim_scope"],
            summary["agent_behavior"]["online"]["claim_scope"],
        )

    def test_merge_replaces_corrected_cases_and_recomputes_pass_at_k(self):
        original = self._agent_report("real_llm_fault_fixture", [False, True])
        original["results"][0]["case_id"] = "fixed"
        original["results"][1]["case_id"] = "stable"
        correction = self._agent_report("real_llm_fault_fixture", [True, True, True])
        for index, row in enumerate(correction["results"], start=1):
            row["case_id"] = "fixed"
            row["attempt"] = index

        merged = merge_agent_benchmark_reports(original, correction)

        self.assertEqual(merged["task_count"], 2)
        self.assertEqual(merged["attempt_count"], 4)
        self.assertEqual(merged["pass_at_1"], 1.0)
        self.assertEqual(merged["pass_at_3"], 1.0)
        self.assertEqual(len([r for r in merged["results"] if r["case_id"] == "fixed"]), 3)

    def test_writer_creates_json_markdown_and_research_style_plots(self):
        scripted = self._agent_report("scripted_fixture", [True, True])
        online = self._agent_report("real_llm_fault_fixture", [True, False])
        trials = [
            {"method": "random_search", "seed": 7, "trial_index": 0, "nmse_db": -30.0, "metric_name": "nmse_db"},
            {"method": "random_search", "seed": 7, "trial_index": 1, "nmse_db": -31.0, "metric_name": "nmse_db"},
            {"method": "agent", "seed": 7, "trial_index": 0, "nmse_db": -32.0, "metric_name": "nmse_db"},
            {"method": "agent", "seed": 7, "trial_index": 1, "nmse_db": -34.0, "metric_name": "nmse_db"},
        ]
        with TemporaryDirectory() as tmpdir:
            paths = write_evidence_pack(
                Path(tmpdir), scripted, online,
                {"per_method": {"random_search": {}, "agent": {}}},
                trials, {"pass": True, "duplicate_execution_rate": 0.0},
                online_before=self._agent_report("real_llm_fault_fixture", [True, False, False, True]),
                before={"target_hit_rate": 0.5, "planner_success_rate": 0.15, "rejected_rate": 0.85, "best_nmse_db": -37.42},
                after={"target_hit_rate": 0.9, "planner_success_rate": 0.93, "rejected_rate": 0.074, "best_nmse_db": -42.43},
            )
            names = {path.name for path in paths}
            payload = json.loads((Path(tmpdir) / "evidence-summary.json").read_text(encoding="utf-8"))
            markdown = (Path(tmpdir) / "evidence-report.md").read_text(encoding="utf-8")

        self.assertIn("evidence-summary.json", names)
        self.assertIn("evidence-report.md", names)
        self.assertIn("agent-pass-rate.png", names)
        self.assertIn("search-convergence.png", names)
        self.assertIn("engineering-improvement.png", names)
        self.assertEqual(payload["agent_behavior"]["online"]["pass_at_1"], 0.5)
        self.assertEqual(payload["agent_behavior"]["online_before"]["pass_at_1"], 0.5)
        self.assertIn("Search quality", markdown)
        self.assertIn("random_search", markdown)
        self.assertIn("Claim policy", markdown)


if __name__ == "__main__":
    unittest.main()

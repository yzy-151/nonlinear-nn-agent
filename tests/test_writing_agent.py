from __future__ import annotations

import json
import unittest

from tests.test_reporting_tool import _task_source, _three_round_task_source


def _narrative_response(nmse: float = -37.49) -> str:
    sections = {
        "executive_summary": {
            "text": f"最优候选达到 {nmse} dB，并满足参数预算。",
            "evidence_refs": ["metric:exp016", "constraint:parameter_count_max"],
        },
        "architecture_analysis": {
            "text": "模型由复数输入、记忆展开、自适应样条和线性读出组成。",
            "evidence_refs": ["architecture:adaptive_wavelet_lut"],
        },
        "performance_analysis": {
            "text": "最优实验相对 -21.83 dB 基线有明确改善。",
            "evidence_refs": ["metric:exp016"],
        },
        "round_journey": {
            "text": "当前夹具未提供多轮决策记录，报告只陈述已有执行证据。",
            "evidence_refs": ["aggregate:performance"],
        },
        "failure_analysis": {
            "text": "一次候选因非法字段被确定性闸门拒绝。",
            "evidence_refs": ["failure:exp_021"],
        },
        "lessons": {
            "text": "后续实验应保留证据引用并围绕有效记忆结构迭代。",
            "evidence_refs": ["plan:hypotheses", "metric:exp016"],
        },
        "limitations": {
            "text": "结论只覆盖当前非线性建模域。",
            "evidence_refs": ["task:limits"],
        },
    }
    return json.dumps(
        {
            "schema_version": 1,
            "task_id": "tool-task-001",
            "sections": sections,
        },
        ensure_ascii=False,
    )


class _Router:
    def __init__(self, response: str):
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def complete(self, role: str, prompt: str) -> str:
        self.calls.append((role, prompt))
        return self.response


class _SequenceRouter:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, role, prompt):
        self.calls.append((role, prompt))
        return self.responses.pop(0)


class WritingAgentTest(unittest.TestCase):
    def test_writing_agent_repairs_one_fidelity_failure(self):
        from nonlinear_agent.writing_agent import EvidenceBundle, WritingAgent

        invalid = json.loads(_narrative_response())
        invalid["sections"]["limitations"] = {
            "text": "当前结果为 -37.49 dB，但结论只覆盖当前域。",
            "evidence_refs": ["task:limits"],
        }
        router = _SequenceRouter(
            [json.dumps(invalid, ensure_ascii=False), _narrative_response()]
        )

        narrative = WritingAgent(model_router=router).write(
            EvidenceBundle.from_task_source(_task_source())
        )

        self.assertEqual(len(router.calls), 2)
        self.assertIn("unsupported number -37.49", router.calls[1][1])
        self.assertIn("Repair the narrative", router.calls[1][1])
        self.assertEqual(
            narrative.sections["limitations"].evidence_refs,
            ("task:limits",),
        )

    def test_round_journey_falls_back_to_all_recorded_rounds_after_failed_repair(self):
        import tempfile
        from pathlib import Path

        from nonlinear_agent.writing_agent import (
            EvidenceBundle,
            NarrativeFidelityError,
            WritingAgent,
        )

        with tempfile.TemporaryDirectory() as td:
            bundle = EvidenceBundle.from_task_source(
                _three_round_task_source(Path(td))
            )
        payload = json.loads(_narrative_response(nmse=-38.5))
        payload["sections"]["executive_summary"]["evidence_refs"] = [
            "final:r3-exp3-final",
            "constraint:parameter_count_max",
        ]
        payload["sections"]["architecture_analysis"]["evidence_refs"] = [
            "architecture:final_unseen_model"
        ]
        payload["sections"]["performance_analysis"]["evidence_refs"] = [
            "final:r3-exp3-final"
        ]
        payload["sections"]["lessons"]["evidence_refs"] = [
            "round:1:decision"
        ]
        payload["sections"]["round_journey"] = {
            "text": "三轮实验根据前序事实逐步收敛。",
            "evidence_refs": ["round:1:decision", "round:2:decision"],
        }

        narrative = WritingAgent(model_router=_Router(json.dumps(payload))).write(bundle)

        self.assertEqual(
            narrative.sections["round_journey"].evidence_refs,
            ("round:1:decision", "round:2:decision", "round:3:decision"),
        )

    def test_round_and_final_evidence_selects_final_descriptor(self):
        import tempfile
        from pathlib import Path

        from nonlinear_agent.writing_agent import EvidenceBundle

        with tempfile.TemporaryDirectory() as td:
            bundle = EvidenceBundle.from_task_source(
                _three_round_task_source(Path(td))
            )

        self.assertEqual(bundle.architecture.name, "final_unseen_model")
        self.assertIn("round:1:decision", bundle.evidence_ids)
        self.assertIn("round:2:decision", bundle.evidence_ids)
        self.assertIn("round:3:decision", bundle.evidence_ids)
        self.assertIn("final:r3-exp3-final", bundle.evidence_ids)
        self.assertIn("artifact:psd:r3-exp3-final", bundle.evidence_ids)

    def test_evidence_bundle_builds_arbitrary_descriptor_graph(self):
        from nonlinear_agent.writing_agent import EvidenceBundle

        bundle = EvidenceBundle.from_task_source(_task_source())

        self.assertEqual(bundle.architecture.name, "adaptive_wavelet_lut")
        self.assertEqual(
            [node.label for node in bundle.architecture.nodes],
            ["Complex Input", "Memory Bank", "Adaptive Wavelet LUT", "Linear Readout"],
        )
        self.assertIn("architecture:adaptive_wavelet_lut", bundle.evidence_ids)
        self.assertIn("metric:exp016", bundle.evidence_ids)

    def test_missing_descriptor_is_explicit_instead_of_guessed_from_model_name(self):
        from nonlinear_agent.writing_agent import EvidenceBundle

        source = _task_source()
        source["executions"][1].pop("model_descriptor")
        bundle = EvidenceBundle.from_task_source(source)

        self.assertFalse(bundle.architecture.descriptor_available)
        self.assertEqual(bundle.architecture.nodes[0].label, "Descriptor unavailable")
        self.assertNotIn("hidden", bundle.architecture.nodes[0].operation.lower())

    def test_writing_agent_uses_writing_role_and_returns_cited_sections(self):
        from nonlinear_agent.writing_agent import EvidenceBundle, WritingAgent

        router = _Router(_narrative_response())
        narrative = WritingAgent(model_router=router).write(
            EvidenceBundle.from_task_source(_task_source())
        )

        self.assertEqual([role for role, _ in router.calls], ["writing"])
        self.assertIn("ModelDescriptor", router.calls[0][1])
        self.assertEqual(
            narrative.sections["architecture_analysis"].evidence_refs,
            ("architecture:adaptive_wavelet_lut",),
        )

    def test_writing_agent_falls_back_after_repeated_unsupported_numeric_claim(self):
        from nonlinear_agent.writing_agent import EvidenceBundle, WritingAgent

        router = _Router(_narrative_response(nmse=-99.0))
        narrative = WritingAgent(model_router=router).write(
            EvidenceBundle.from_task_source(_task_source())
        )

        self.assertNotIn("-99.0", narrative.sections["executive_summary"].text)
        self.assertEqual(len(router.calls), 2)

    def test_writing_agent_falls_back_after_repeated_unknown_evidence_reference(self):
        from nonlinear_agent.writing_agent import EvidenceBundle, WritingAgent

        payload = json.loads(_narrative_response())
        payload["sections"]["lessons"]["evidence_refs"] = ["memory:invented"]
        bundle = EvidenceBundle.from_task_source(_task_source())
        narrative = WritingAgent(model_router=_Router(json.dumps(payload))).write(bundle)

        self.assertTrue(
            all(
                ref in bundle.evidence_ids
                for section in narrative.sections.values()
                for ref in section.evidence_refs
            )
        )

    def test_numeric_claim_with_wrong_section_evidence_uses_safe_fallback(self):
        from nonlinear_agent.writing_agent import EvidenceBundle, WritingAgent

        payload = json.loads(_narrative_response())
        payload["sections"]["executive_summary"] = {
            "text": "最优候选达到 -21.83 dB。",
            "evidence_refs": ["constraint:parameter_count_max"],
        }
        narrative = WritingAgent(model_router=_Router(json.dumps(payload))).write(
            EvidenceBundle.from_task_source(_task_source())
        )

        self.assertNotIn("-21.83", narrative.sections["executive_summary"].text)

    def test_failure_line_numbers_are_supported_by_the_cited_failure_fact(self):
        from nonlinear_agent.writing_agent import EvidenceBundle, WritingAgent

        source = _task_source()
        source["failure_cases"][0]["error"] = "static gate failed at line 8"
        payload = json.loads(_narrative_response())
        payload["sections"]["failure_analysis"] = {
            "text": "静态门禁在第 8 行拒绝了模块顶层调用。",
            "evidence_refs": ["failure:exp_021"],
        }

        narrative = WritingAgent(model_router=_Router(json.dumps(payload))).write(
            EvidenceBundle.from_task_source(source)
        )

        self.assertIn("第 8 行", narrative.sections["failure_analysis"].text)

    def test_aggregate_performance_carries_the_target_threshold(self):
        from nonlinear_agent.writing_agent import EvidenceBundle

        bundle = EvidenceBundle.from_task_source(_task_source())

        aggregate = bundle.records["aggregate:performance"]["value"]
        self.assertEqual(aggregate["nmse_threshold_db"], -35.0)

    def test_architecture_evidence_carries_derived_node_and_edge_counts(self):
        from nonlinear_agent.writing_agent import EvidenceBundle

        bundle = EvidenceBundle.from_task_source(_task_source())

        value = bundle.records["architecture:adaptive_wavelet_lut"]["value"]
        self.assertEqual(value["node_count"], len(value["nodes"]))
        self.assertEqual(value["edge_count"], len(value["edges"]))

    def test_deterministic_fallback_does_not_copy_uncited_legacy_analysis(self):
        from nonlinear_agent.writing_agent import EvidenceBundle, build_deterministic_narrative

        source = _task_source()
        bundle = EvidenceBundle.from_task_source(source)
        narrative = build_deterministic_narrative(
            bundle,
            source,
            legacy_analysis={"experience": "未经证据支持的 999.0 dB 结论"},
        )

        self.assertNotIn("999.0", narrative.sections["lessons"].text)


if __name__ == "__main__":
    unittest.main()

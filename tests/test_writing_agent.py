from __future__ import annotations

import json
import unittest

from tests.test_reporting_tool import _task_source


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


class WritingAgentTest(unittest.TestCase):
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

    def test_writing_agent_rejects_unsupported_numeric_claim(self):
        from nonlinear_agent.writing_agent import EvidenceBundle, NarrativeFidelityError, WritingAgent

        router = _Router(_narrative_response(nmse=-99.0))
        with self.assertRaisesRegex(NarrativeFidelityError, "unsupported number"):
            WritingAgent(model_router=router).write(
                EvidenceBundle.from_task_source(_task_source())
            )

    def test_writing_agent_rejects_unknown_evidence_reference(self):
        from nonlinear_agent.writing_agent import EvidenceBundle, NarrativeFidelityError, WritingAgent

        payload = json.loads(_narrative_response())
        payload["sections"]["lessons"]["evidence_refs"] = ["memory:invented"]
        with self.assertRaisesRegex(NarrativeFidelityError, "unknown evidence"):
            WritingAgent(model_router=_Router(json.dumps(payload))).write(
                EvidenceBundle.from_task_source(_task_source())
            )

    def test_numeric_claim_must_come_from_the_sections_cited_evidence(self):
        from nonlinear_agent.writing_agent import EvidenceBundle, NarrativeFidelityError, WritingAgent

        payload = json.loads(_narrative_response())
        payload["sections"]["executive_summary"] = {
            "text": "最优候选达到 -21.83 dB。",
            "evidence_refs": ["constraint:parameter_count_max"],
        }
        with self.assertRaisesRegex(NarrativeFidelityError, "not supported by cited evidence"):
            WritingAgent(model_router=_Router(json.dumps(payload))).write(
                EvidenceBundle.from_task_source(_task_source())
            )

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

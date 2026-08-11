"""Evidence-grounded Writing Agent for dynamic experiment reports."""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from typing import Any

from nonlinear_agent.model_plugins.contracts import (
    ArchitectureEdge,
    ArchitectureNode,
    ModelDescriptor,
    validate_descriptor,
)
from nonlinear_agent.reporting.task_report_spec import TaskReportBuilder


REQUIRED_NARRATIVE_SECTIONS = (
    "executive_summary",
    "architecture_analysis",
    "performance_analysis",
    "round_journey",
    "failure_analysis",
    "lessons",
    "limitations",
)
_NUMBER = re.compile(r"(?<![A-Za-z0-9_])[-+]?\d+(?:\.\d+)?(?![A-Za-z0-9_])")


@dataclass(frozen=True)
class ArchitectureGraphSpec:
    name: str
    version: str
    training_mode: str
    nodes: tuple[ArchitectureNode, ...]
    edges: tuple[ArchitectureEdge, ...]
    descriptor_available: bool = True

    @classmethod
    def from_dict(
        cls, value: dict[str, Any] | None, fallback_name: str = "unknown"
    ) -> "ArchitectureGraphSpec":
        if not value:
            return cls(
                name=fallback_name or "unknown",
                version="unknown",
                training_mode="unknown",
                nodes=(
                    ArchitectureNode(
                        node_id="missing",
                        label="Descriptor unavailable",
                        operation="unknown",
                        details={},
                    ),
                ),
                edges=(),
                descriptor_available=False,
            )
        descriptor = ModelDescriptor.from_dict(value)
        validate_descriptor(descriptor)
        if not descriptor.nodes:
            raise ValueError("model descriptor must contain architecture nodes")
        return cls(
            name=descriptor.name,
            version=descriptor.version,
            training_mode=descriptor.training_mode,
            nodes=descriptor.nodes,
            edges=descriptor.edges,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceBundle:
    task_id: str
    goal: str
    constraints: dict[str, Any]
    architecture: ArchitectureGraphSpec
    records: dict[str, dict[str, Any]]
    evidence_ids: frozenset[str]
    allowed_numbers: tuple[float, ...]

    @classmethod
    def from_task_source(cls, source: dict[str, Any]) -> "EvidenceBundle":
        spec = TaskReportBuilder().build(source)
        if not spec.executions:
            raise ValueError("task source has no executions")
        best = spec.best()
        selected = spec.selected()
        final_source = source.get("final_evaluation")
        if spec.final_evaluation is not None and isinstance(final_source, dict):
            best_source = dict(final_source)
        else:
            best_source = next(
                (
                    item
                    for item in source.get("executions", [])
                    if selected is not None and str(item.get("run_id")) == selected.run_id
                ),
                {},
            )
        architecture = ArchitectureGraphSpec.from_dict(
            best_source.get("model_descriptor") or best_source.get("descriptor"),
            fallback_name=str(best_source.get("model_type", "unknown")),
        )

        records: dict[str, dict[str, Any]] = {
            "task:goal": {"kind": "goal", "value": spec.goal},
            "task:limits": {"kind": "limits", "value": spec.limits},
            "plan:hypotheses": {
                "kind": "plan",
                "value": list(spec.plan.get("hypotheses", [])),
            },
            f"architecture:{architecture.name}": {
                "kind": "model_descriptor",
                "value": {
                    **architecture.to_dict(),
                    "node_count": len(architecture.nodes),
                    "edge_count": len(architecture.edges),
                },
            },
        }
        for key, value in spec.constraints.items():
            records[f"constraint:{key}"] = {
                "kind": "constraint",
                "value": value,
            }
        for item in source.get("executions", []):
            run_id = str(item.get("run_id", "unknown"))
            records[f"metric:{run_id}"] = {
                "kind": "execution_metrics",
                "value": {
                    key: item.get(key)
                    for key in (
                        "run_id",
                        "model_type",
                        "nmse_db",
                        "baseline_nmse_db",
                        "parameter_count",
                        "target_hit",
                        "cost_usd",
                        "config",
                    )
                    if key in item
                },
            }
            if item.get("psd_path"):
                records[f"artifact:psd:{run_id}"] = {
                    "kind": "artifact",
                    "value": {"type": "psd", "path": str(item["psd_path"])},
                }
        if spec.final_evaluation is not None and isinstance(final_source, dict):
            final_id = spec.final_evaluation.run_id
            records[f"final:{final_id}"] = {
                "kind": "final_evaluation",
                "value": dict(final_source),
            }
            if final_source.get("psd_path"):
                records[f"artifact:psd:{final_id}"] = {
                    "kind": "artifact",
                    "value": {
                        "type": "psd",
                        "path": str(final_source["psd_path"]),
                        "evaluation_kind": "final",
                        "run_id": final_id,
                    },
                }
        for index, item in enumerate(source.get("round_records", []), start=1):
            round_index = int(item.get("round_index", index))
            records[f"round:{round_index}:decision"] = {
                "kind": "round_decision",
                "value": dict(item),
            }
        for item in source.get("failure_cases", []):
            failure_id = str(item.get("id", "unknown"))
            records[f"failure:{failure_id}"] = {
                "kind": "failure",
                "value": dict(item),
            }
        for index, value in enumerate(source.get("trace_refs", []), start=1):
            records[f"trace:{index}"] = {"kind": "trace", "value": str(value)}

        nmse_values = [
            run.nmse_db for run in spec.executions if run.nmse_db is not None
        ]
        hit_count = sum(1 for run in spec.executions if run.target_hit)
        aggregate = {
            "execution_count": len(spec.executions),
            "search_execution_count": len(spec.executions),
            "round_count": len(spec.round_records),
            "final_evaluation_count": 1 if spec.final_evaluation is not None else 0,
            "target_hit_count": hit_count,
            "target_hit_rate_percent": (
                100.0 * hit_count / len(spec.executions) if spec.executions else 0.0
            ),
            "average_nmse_db": (
                sum(nmse_values) / len(nmse_values) if nmse_values else None
            ),
            "best_gain_db": (
                best.baseline_nmse_db - best.nmse_db
                if best
                and best.baseline_nmse_db is not None
                and best.nmse_db is not None
                else None
            ),
            "architecture_node_count": len(architecture.nodes),
            "nmse_threshold_db": spec.constraints.get("nmse_threshold_db"),
            "parameter_count_max": spec.constraints.get("parameter_count_max"),
        }
        records["aggregate:performance"] = {
            "kind": "derived_metrics",
            "value": aggregate,
        }
        numbers = _collect_numbers(source)
        numbers.extend(_collect_numbers(aggregate))
        return cls(
            task_id=spec.task_id,
            goal=spec.goal,
            constraints=dict(spec.constraints),
            architecture=architecture,
            records=records,
            evidence_ids=frozenset(records),
            allowed_numbers=tuple(sorted(set(numbers))),
        )

    def to_prompt_payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "constraints": self.constraints,
            "ModelDescriptor": self.architecture.to_dict(),
            "evidence_records": self.records,
        }


@dataclass(frozen=True)
class NarrativeSection:
    text: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class NarrativeSpec:
    task_id: str
    sections: dict[str, NarrativeSection]

    @classmethod
    def from_json(cls, value: str) -> "NarrativeSpec":
        stripped = value.strip()
        if not stripped.startswith("{") or not stripped.endswith("}"):
            raise ValueError("writing response must be one JSON object")
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"writing response is invalid JSON: {exc}") from exc
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NarrativeSpec":
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("narrative schema_version must be 1")
        expected = {"schema_version", "task_id", "sections"}
        if set(payload) != expected:
            raise ValueError("narrative top-level fields do not match schema")
        if not str(payload.get("task_id", "")).strip():
            raise ValueError("narrative task_id must not be empty")
        raw_sections = payload.get("sections")
        if not isinstance(raw_sections, dict):
            raise ValueError("narrative sections must be an object")
        missing = sorted(set(REQUIRED_NARRATIVE_SECTIONS) - set(raw_sections))
        unknown = sorted(set(raw_sections) - set(REQUIRED_NARRATIVE_SECTIONS))
        if missing:
            raise ValueError(f"narrative missing sections: {', '.join(missing)}")
        if unknown:
            raise ValueError(f"narrative has unknown sections: {', '.join(unknown)}")
        sections: dict[str, NarrativeSection] = {}
        for name in REQUIRED_NARRATIVE_SECTIONS:
            raw = raw_sections[name]
            if not isinstance(raw, dict) or set(raw) != {"text", "evidence_refs"}:
                raise ValueError(f"narrative section {name} has invalid fields")
            text = str(raw["text"]).strip()
            refs = raw["evidence_refs"]
            if not text or len(text) > 3000:
                raise ValueError(f"narrative section {name} text is invalid")
            if not isinstance(refs, list) or not refs:
                raise ValueError(f"narrative section {name} requires evidence_refs")
            sections[name] = NarrativeSection(
                text=text,
                evidence_refs=tuple(str(ref) for ref in refs),
            )
        return cls(task_id=str(payload.get("task_id", "")), sections=sections)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "task_id": self.task_id,
            "sections": {
                name: {
                    "text": section.text,
                    "evidence_refs": list(section.evidence_refs),
                }
                for name, section in self.sections.items()
            },
        }


class NarrativeFidelityError(ValueError):
    pass


class NarrativeFidelityChecker:
    def check(
        self, narrative: NarrativeSpec, bundle: EvidenceBundle
    ) -> list[str]:
        errors: list[str] = []
        if narrative.task_id != bundle.task_id:
            errors.append("narrative task_id does not match evidence bundle")
        for name, section in narrative.sections.items():
            unknown = sorted(set(section.evidence_refs) - bundle.evidence_ids)
            if unknown:
                errors.append(
                    f"{name}: unknown evidence refs: {', '.join(unknown)}"
                )
            cited_numbers = tuple(
                number
                for ref in section.evidence_refs
                if ref in bundle.records
                for number in _collect_numbers(bundle.records[ref])
            )
            for match in _NUMBER.finditer(section.text):
                claim = float(match.group())
                decimals = len(match.group().partition(".")[2])
                tolerance = max(1e-9, 0.5 * (10 ** -decimals))
                if not any(
                    math.isclose(claim, known, rel_tol=0.0, abs_tol=tolerance)
                    for known in cited_numbers
                ):
                    errors.append(
                        f"{name}: unsupported number {match.group()} "
                        "(not supported by cited evidence)"
                    )
        round_refs = {
            evidence_id
            for evidence_id, record in bundle.records.items()
            if record.get("kind") == "round_decision"
        }
        if round_refs:
            cited = set(narrative.sections["round_journey"].evidence_refs)
            missing_rounds = sorted(round_refs - cited)
            if missing_rounds:
                errors.append(
                    "round_journey must cite every round: "
                    + ", ".join(missing_rounds)
                )
        return errors


class WritingAgent:
    def __init__(
        self,
        llm_client: Any | None = None,
        model_router: Any | None = None,
        model_role: str = "writing",
    ):
        self._llm = llm_client
        self._router = model_router
        self._role = model_role

    def write(self, bundle: EvidenceBundle) -> NarrativeSpec:
        if self._llm is None and self._router is None:
            raise RuntimeError("WritingAgent requires an LLM client or ModelRouter")
        prompt = _writing_prompt(bundle)
        response = self._complete(prompt)
        narrative = NarrativeSpec.from_json(str(response))
        errors = NarrativeFidelityChecker().check(narrative, bundle)
        if errors:
            repair_prompt = (
                prompt
                + "\n\nPrevious narrative:\n"
                + str(response)
                + "\n\nFidelity errors:\n- "
                + "\n- ".join(errors)
                + "\nRepair the narrative by changing unsupported claims or adding "
                "the exact evidence_refs that support them. Return the complete JSON "
                "object only."
            )
            repaired = NarrativeSpec.from_json(str(self._complete(repair_prompt)))
            repaired_errors = NarrativeFidelityChecker().check(repaired, bundle)
            if repaired_errors:
                raise NarrativeFidelityError("; ".join(repaired_errors))
            return repaired
        return narrative

    def _complete(self, prompt: str) -> Any:
        if self._router is not None:
            return self._router.complete(self._role, prompt)
        return self._llm.complete(prompt)


def build_deterministic_narrative(
    bundle: EvidenceBundle,
    source: dict[str, Any],
    legacy_analysis: dict[str, str] | None = None,
) -> NarrativeSpec:
    """Evidence-only fallback used when no writing-model output was supplied."""
    del legacy_analysis  # Kept in the signature for compatibility; prose must come from evidence.
    spec = TaskReportBuilder().build(source)
    best = spec.best()
    best_ref = f"metric:{best.run_id}" if best else "aggregate:performance"
    architecture_ref = f"architecture:{bundle.architecture.name}"
    labels = "、".join(node.label for node in bundle.architecture.nodes)
    gain = (
        best.baseline_nmse_db - best.nmse_db
        if best and best.baseline_nmse_db is not None and best.nmse_db is not None
        else None
    )
    summary = (
        f"最优候选 {best.model_type} 的 NMSE 为 {best.nmse_db:.4f} dB，"
        f"参数量为 {best.parameter_count}。"
        if best and best.nmse_db is not None
        else "当前证据没有可比较的最优 NMSE。"
    )
    failures = list(source.get("failure_cases", []))
    failure_refs = tuple(
        f"failure:{item.get('id', 'unknown')}" for item in failures
    ) or ("aggregate:performance",)
    failure_text = (
        "；".join(
            str(item.get("错误", item.get("error", "已记录失败")))
            for item in failures
        )
        if failures
        else "当前任务没有记录失败案例。"
    )
    sections = {
        "executive_summary": NarrativeSection(summary, (best_ref,)),
        "architecture_analysis": NarrativeSection(
            f"模型描述符给出的实际处理节点为：{labels}。",
            (architecture_ref,),
        ),
        "performance_analysis": NarrativeSection(
            (
                (
                    f"最优 NMSE 为 {best.nmse_db:.4f} dB。"
                    + (f"相对基线改善 {gain:.2f} dB。" if gain is not None else "")
                )
                if best and best.nmse_db is not None
                else "当前证据不足以计算相对基线改善。"
            ),
            (best_ref, "aggregate:performance"),
        ),
        "round_journey": NarrativeSection(
            (
                "各轮的假设、候选结果、事实提取和下一轮意图均按结构化记录展示。"
                if source.get("round_records")
                else "当前证据没有提供多轮决策记录。"
            ),
            tuple(
                f"round:{int(item.get('round_index', index))}:decision"
                for index, item in enumerate(source.get("round_records", []), start=1)
            ) or ("aggregate:performance",),
        ),
        "failure_analysis": NarrativeSection(failure_text, failure_refs),
        "lessons": NarrativeSection(
            "后续迭代应继续保留计划、执行、失败和产物之间的证据引用。",
            ("plan:hypotheses", best_ref),
        ),
        "limitations": NarrativeSection(
            str(source.get("limits") or "当前报告只对已提供证据负责。"),
            ("task:limits",),
        ),
    }
    return NarrativeSpec(task_id=bundle.task_id, sections=sections)


def _writing_prompt(bundle: EvidenceBundle) -> str:
    schema = {
        "schema_version": 1,
        "task_id": bundle.task_id,
        "sections": {
            name: {"text": "evidence-grounded Chinese prose", "evidence_refs": ["evidence:id"]}
            for name in REQUIRED_NARRATIVE_SECTIONS
        },
    }
    return (
        "You are the WritingAgent. Produce a concise professional Chinese "
        "experiment narrative from the supplied ModelDescriptor, metrics, "
        "artifacts, failures, plan, and traces. Return one JSON object only. "
        "Every section must cite existing evidence IDs. Do not state a number "
        "unless it appears in the evidence payload. Describe the actual graph "
        "nodes and operations; never infer architecture from a model name. "
        "When round_decision evidence exists, round_journey must explain the "
        "hypothesis, three attempts, observed facts, and next adjustment while "
        "citing every round decision record.\n\n"
        f"EvidenceBundle:\n{json.dumps(bundle.to_prompt_payload(), ensure_ascii=False, sort_keys=True)}\n\n"
        f"Required schema:\n{json.dumps(schema, ensure_ascii=False)}"
    )


def _collect_numbers(value: Any) -> list[float]:
    numbers: list[float] = []
    if isinstance(value, bool) or value is None:
        return numbers
    if isinstance(value, (int, float)):
        number = float(value)
        if math.isfinite(number):
            numbers.append(number)
        return numbers
    if isinstance(value, str):
        return [float(match.group()) for match in _NUMBER.finditer(value)]
    if isinstance(value, dict):
        for item in value.values():
            numbers.extend(_collect_numbers(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            numbers.extend(_collect_numbers(item))
    return numbers

"""PlanGate — IdeaPlanSpec schema validation, dedup and citation coverage (v3.7.0)."""

from __future__ import annotations

from typing import Any


REQUIRED_HYPOTHESIS_FIELDS = ("hypothesis", "rationale", "citation")
REQUIRED_CANDIDATE_FIELDS = (
    "model_type",
    "params_estimate",
    "budget",
    "stop_condition",
    "rationale",
    "citation",
)
REQUIRED_BUDGET_FIELDS = ("parameter_count_max", "epochs_max")
REQUIRED_PLAN_FIELDS = (
    "plan_id",
    "hypotheses",
    "candidate_experiments",
    "experiment_dag",
    "expected_information_gain",
    "risk",
    "fallback",
    "required_code_changes",
)


class PlanGate:
    """Deterministic gate between Idea/Plan Agent output and execution."""

    def validate(
        self,
        plan: dict[str, Any],
        parameter_count_max: int | None = None,
        available_citation_ids: set[str] | None = None,
    ) -> list[str]:
        errors: list[str] = []
        for field in REQUIRED_PLAN_FIELDS:
            if field not in plan:
                errors.append(f"missing plan field: {field}")
        if "hypotheses" in plan and not isinstance(plan["hypotheses"], list):
            errors.append("hypotheses must be a list")
        if "candidate_experiments" in plan and not isinstance(
            plan["candidate_experiments"], list
        ):
            errors.append("candidate_experiments must be a list")

        for index, hypothesis in enumerate(plan.get("hypotheses", [])):
            if not isinstance(hypothesis, dict):
                errors.append(f"hypotheses[{index}] must be an object")
                continue
            for field in REQUIRED_HYPOTHESIS_FIELDS:
                if field not in hypothesis:
                    errors.append(
                        f"hypotheses[{index}] missing field: {field}"
                    )
            citation = str(hypothesis.get("citation", "")).strip()
            if available_citation_ids is not None:
                if not citation:
                    errors.append(f"hypotheses[{index}] empty citation")
                elif citation not in available_citation_ids:
                    errors.append(f"hypotheses[{index}] unknown citation: {citation}")

        for index, candidate in enumerate(plan.get("candidate_experiments", [])):
            if not isinstance(candidate, dict):
                errors.append(f"candidate_experiments[{index}] must be an object")
                continue
            for field in REQUIRED_CANDIDATE_FIELDS:
                if field not in candidate:
                    errors.append(
                        f"candidate_experiments[{index}] missing field: {field}"
                    )
            budget = candidate.get("budget")
            if budget is not None:
                if not isinstance(budget, dict):
                    errors.append(f"candidate_experiments[{index}] budget must be an object")
                else:
                    for field in REQUIRED_BUDGET_FIELDS:
                        if field not in budget:
                            errors.append(
                                f"candidate_experiments[{index}] budget missing field: {field}"
                            )
            params = candidate.get("params_estimate")
            if parameter_count_max is not None and isinstance(params, (int, float)):
                if params > parameter_count_max:
                    errors.append(
                        f"candidate_experiments[{index}] params_estimate {params} "
                        f"exceeds budget {parameter_count_max}"
                    )
            citation = str(candidate.get("citation", "")).strip()
            if available_citation_ids is not None:
                if not citation:
                    errors.append(f"candidate_experiments[{index}] empty citation")
                elif citation not in available_citation_ids:
                    errors.append(
                        f"candidate_experiments[{index}] unknown citation: {citation}"
                    )
        return errors

    def validate_batch(
        self,
        plan: dict[str, Any],
        expected_experiments: int,
        round_index: int = 1,
        available_fact_refs: set[str] | None = None,
        available_citation_ids: set[str] | None = None,
    ) -> list[str]:
        """Validate the cross-experiment contract for one search round."""
        errors = self.validate(
            plan,
            available_citation_ids=available_citation_ids,
        )
        candidates = plan.get("candidate_experiments", [])
        if not isinstance(candidates, list):
            return errors
        if len(candidates) != expected_experiments:
            errors.append(
                f"candidate_experiments must contain exactly {expected_experiments} items"
            )

        experiment_ids: list[str] = []
        known_facts = set(available_fact_refs or set())
        for index, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                continue
            for field in (
                "experiment_id",
                "exploration_role",
                "based_on_fact_refs",
                "expected_information_gain",
            ):
                if field not in candidate:
                    errors.append(
                        f"candidate_experiments[{index}] missing batch field: {field}"
                    )
            experiment_id = str(candidate.get("experiment_id", "")).strip()
            if experiment_id:
                experiment_ids.append(experiment_id)
            refs = candidate.get("based_on_fact_refs", [])
            if not isinstance(refs, list):
                errors.append(
                    f"candidate_experiments[{index}] based_on_fact_refs must be a list"
                )
                continue
            if round_index > 1 and not refs:
                errors.append(
                    f"candidate_experiments[{index}] must reference a prior fact"
                )
            for ref in refs:
                if str(ref) not in known_facts:
                    errors.append(
                        f"candidate_experiments[{index}] unknown fact ref: {ref}"
                    )

        if len(experiment_ids) != len(set(experiment_ids)):
            errors.append("candidate experiment_id must be unique")
        return errors

    def is_duplicate(
        self, plan: dict[str, Any], history_hashes: set[str]
    ) -> bool:
        """True when any candidate reuses a historical config hash."""
        return any(
            str(candidate.get("config_hash", "")) in history_hashes
            for candidate in plan.get("candidate_experiments", [])
            if isinstance(candidate, dict)
        )

    def citation_coverage(self, plan: dict[str, Any]) -> float:
        """Ratio of hypotheses+candidates carrying a citation (>=0.90 target)."""
        hypotheses = plan.get("hypotheses", [])
        candidates = plan.get("candidate_experiments", [])
        cited = sum(
            1 for h in hypotheses if isinstance(h, dict) and h.get("citation")
        ) + sum(
            1
            for c in candidates
            if isinstance(c, dict) and c.get("citation")
        )
        total = len(hypotheses) + len(candidates)
        return cited / total if total else 1.0

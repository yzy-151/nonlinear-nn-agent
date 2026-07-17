"""Historical-prior knowledge base for search/reflection strategies.

Loads hand-verified best candidates (from prior DeepSeek runs, model-search
results, and reports) so that knowledge-based strategies (e.g.
llm_with_reflection) can start from known-good regions instead of exploring
from scratch. Priors are filtered by the active parameter budget and sorted
best-first by the known metric.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_PRIOR_PATH = Path("configs/priors/nonlinear-modeling.json")


@dataclass(frozen=True)
class HistoricalPrior:
    """One historical best candidate."""

    id: str
    overrides: dict[str, Any]
    known_nmse_db: float
    parameter_count: int
    source: str = ""


def load_historical_priors(
    path: Path | None = None, parameter_count_max: int | None = None
) -> list[HistoricalPrior]:
    """Load priors, filter to the parameter budget, sort best-first.

    `parameter_count_max` defaults to the value stored in the JSON file.
    """
    path = path or DEFAULT_PRIOR_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    budget = parameter_count_max if parameter_count_max is not None else int(
        data.get("parameter_count_max", 20000)
    )

    priors: list[HistoricalPrior] = []
    for item in data.get("candidates", []):
        parameter_count = int(item.get("parameter_count", 0))
        if parameter_count > budget:
            continue
        overrides = {
            key: value
            for key, value in item.items()
            if key
            not in (
                "id",
                "known_nmse_db",
                "parameter_count",
                "source",
            )
        }
        priors.append(
            HistoricalPrior(
                id=str(item["id"]),
                overrides=overrides,
                known_nmse_db=float(item["known_nmse_db"]),
                parameter_count=parameter_count,
                source=str(item.get("source", "")),
            )
        )

    priors.sort(key=lambda p: p.known_nmse_db)
    return priors

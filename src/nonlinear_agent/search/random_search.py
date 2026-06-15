"""Seeded random search strategy.

Uniformly samples candidates from the domain's design space using a
seeded random.Random instance. Duplicate candidates are detected via
SHA-256 hash and resampled (up to 20 attempts).
"""

from __future__ import annotations

import hashlib
import json
import random
from typing import Any

from nonlinear_agent.search.base import SearchContext


class RandomSearch:
    """Random search with seed reproducibility and duplicate detection."""

    name = "random_search"

    def __init__(self, context: SearchContext):
        self._ctx = context
        self._rng = random.Random(context.seed)
        self._seen_hashes: set[str] = set()
        self._duplicate_retries = 20
        self._exhausted = False

    def suggest(
        self, history: list[dict], trial_index: int
    ) -> dict[str, Any]:
        if self._exhausted:
            return {}

        design_space = self._ctx.domain.design_space()

        for _attempt in range(self._duplicate_retries):
            candidate = {}
            for field, choices in design_space.items():
                candidate[field] = self._rng.choice(choices)

            h = _hash_candidate(candidate)
            if h not in self._seen_hashes:
                self._seen_hashes.add(h)
                return candidate

        self._exhausted = True
        return {}

    def observe(self, candidate: dict, result: dict) -> None:
        pass  # Random search does not learn from outcomes


def _hash_candidate(candidate: dict) -> str:
    raw = json.dumps(candidate, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()

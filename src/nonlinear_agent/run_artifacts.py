from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from nonlinear_agent.planner import ExperimentPlan


LEADERBOARD_COLUMNS = [
    "rank",
    "id",
    "run_status",
    "nmse_db",
    "parameter_count",
    "model_type",
    "feature_mode",
    "memory_depth",
    "mp_order_count",
    "epochs",
    "error",
]


def default_run_dir(workspace: Path, clock: Any | None = None) -> Path:
    now = clock() if clock else datetime.now()
    return workspace / "runs" / now.strftime("%Y%m%d-%H%M%S-planner-loop")


class RunArtifactWriter:
    def __init__(self, run_dir: Path | str):
        self.run_dir = Path(run_dir)
        self.plans_dir = self.run_dir / "plans"

    def write_plan(self, round_index: int, plan: ExperimentPlan) -> None:
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "round": round_index,
            "summary": plan.summary,
            "stop": plan.stop,
            "experiments": [
                {
                    "id": experiment.experiment_id,
                    "reason": experiment.reason,
                    "overrides": experiment.overrides,
                }
                for experiment in plan.experiments
            ],
        }
        self._write_json(self.plans_dir / f"round-{round_index:03d}.json", payload)

    def write_result(self, result: Any) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        payload = asdict(result) if hasattr(result, "__dataclass_fields__") else dict(result)
        self._write_json(self.run_dir / "result.json", payload)
        leaderboard = build_leaderboard(payload.get("history", []))
        self._write_leaderboard(leaderboard)
        self._write_summary(payload, leaderboard)

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_leaderboard(self, rows: list[dict[str, Any]]) -> None:
        path = self.run_dir / "leaderboard.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=LEADERBOARD_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({column: row.get(column, "") for column in LEADERBOARD_COLUMNS})

    def _write_summary(self, result: dict[str, Any], leaderboard: list[dict[str, Any]]) -> None:
        lines = [
            "# Planner Loop Summary",
            "",
            f"Status: `{result.get('status', '')}`",
            "",
            f"Rounds: `{result.get('rounds', '')}`",
            "",
            f"History records: `{len(result.get('history', []))}`",
            "",
        ]
        if leaderboard:
            best = leaderboard[0]
            lines.extend(
                [
                    "## Best Candidate",
                    "",
                    f"- id: `{best.get('id', '')}`",
                    f"- nmse_db: `{best.get('nmse_db', '')}`",
                    f"- parameter_count: `{best.get('parameter_count', '')}`",
                    f"- model_type: `{best.get('model_type', '')}`",
                    f"- run_status: `{best.get('run_status', '')}`",
                    "",
                ]
            )
        if result.get("summaries"):
            lines.extend(["## Planner Summaries", ""])
            for index, summary in enumerate(result["summaries"], start=1):
                lines.append(f"{index}. {summary}")
            lines.append("")
        lines.append("See `leaderboard.csv`, `result.json`, and `plans/` for full details.")
        (self.run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_leaderboard(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for record in history:
        row = {column: record.get(column, "") for column in LEADERBOARD_COLUMNS}
        rows.append(row)
    rows.sort(key=_leaderboard_sort_key)
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def _leaderboard_sort_key(row: dict[str, Any]) -> tuple[int, float]:
    try:
        return (0, float(row.get("nmse_db")))
    except (TypeError, ValueError):
        return (1, 0.0)

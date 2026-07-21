from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml


@dataclass(frozen=True)
class ExperimentRecord:
    name: str
    nmse_db: float
    epochs: int
    optimizer: str
    learning_rate: float
    has_psd: bool
    path: Path


def load_experiment_record(experiment_dir: Path | str) -> ExperimentRecord:
    path = Path(experiment_dir)
    metrics_path = path / "metrics.json"
    config_path = path / "resolved_config.yaml"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return ExperimentRecord(
        name=path.name,
        nmse_db=float(metrics["nmse_db"]),
        epochs=int(metrics["epochs"]),
        optimizer=str(config.get("optimizer", "unknown")),
        learning_rate=float(config.get("learning_rate", 0.0)),
        has_psd=(path / "psd.png").exists(),
        path=path,
    )


def rank_experiments(records: Iterable[ExperimentRecord]) -> list[ExperimentRecord]:
    return sorted(records, key=lambda record: record.nmse_db)


def build_comparison_markdown(records: Iterable[ExperimentRecord]) -> str:
    ranked = rank_experiments(records)
    if not ranked:
        raise ValueError("At least one experiment record is required.")
    best = ranked[0]
    rows = [
        "| Experiment | NMSE dB | Epochs | Optimizer | LR | PSD |",
        "|---|---:|---:|---|---:|---|",
    ]
    for record in ranked:
        rows.append(
            "| "
            f"{record.name} | "
            f"{record.nmse_db:.4f} | "
            f"{record.epochs} | "
            f"{record.optimizer} | "
            f"{record.learning_rate:g} | "
            f"{'yes' if record.has_psd else 'no'} |"
        )
    return (
        "# Experiment Comparison\n\n"
        "## Ranking\n\n"
        + "\n".join(rows)
        + "\n\n"
        "## Best Result\n\n"
        f"- Best experiment: `{best.name}`\n"
        f"- Best NMSE: {best.nmse_db:.2f} dB\n"
        f"- PSD artifact: `{(best.path / 'psd.png').as_posix()}`\n\n"
        "## Resume Evidence\n\n"
        "This comparison turns individual training runs into a hiring-facing evidence chain: "
        "the Agent can execute experiments, parse NMSE, verify PSD artifacts, rank results, "
        "and summarize the best configuration for resume and interview discussion.\n"
    )


def write_comparison_report(records: Iterable[ExperimentRecord], output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_comparison_markdown(records), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiments", nargs="+", required=True)
    parser.add_argument("--output", default="docs/experiment-comparison.md")
    args = parser.parse_args()
    records = [load_experiment_record(Path(item)) for item in args.experiments]
    report_path = write_comparison_report(records, Path(args.output))
    print(report_path)


if __name__ == "__main__":
    main()


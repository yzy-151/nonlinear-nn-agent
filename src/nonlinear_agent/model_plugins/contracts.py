"""Stable contracts shared by coding, execution, and writing agents."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol, runtime_checkable


_TRAINING_MODES = {"gradient", "closed_form", "custom"}


@dataclass(frozen=True)
class ArchitectureNode:
    node_id: str
    label: str
    operation: str
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ArchitectureNode":
        return cls(
            node_id=str(value.get("node_id", "")),
            label=str(value.get("label", "")),
            operation=str(value.get("operation", "")),
            details=dict(value.get("details") or {}),
        )


@dataclass(frozen=True)
class ArchitectureEdge:
    source: str
    target: str
    label: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ArchitectureEdge":
        return cls(
            source=str(value.get("source", "")),
            target=str(value.get("target", "")),
            label=str(value.get("label", "")),
        )


@dataclass(frozen=True)
class ModelDescriptor:
    name: str
    version: str
    training_mode: str
    config_schema: dict[str, Any]
    nodes: tuple[ArchitectureNode, ...]
    edges: tuple[ArchitectureEdge, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ModelDescriptor":
        return cls(
            name=str(value.get("name", "")),
            version=str(value.get("version", "")),
            training_mode=str(value.get("training_mode", "")),
            config_schema=dict(value.get("config_schema") or {}),
            nodes=tuple(
                ArchitectureNode.from_dict(item)
                for item in value.get("nodes", [])
            ),
            edges=tuple(
                ArchitectureEdge.from_dict(item)
                for item in value.get("edges", [])
            ),
        )


@dataclass(frozen=True)
class TrainingRequest:
    run_id: str
    workspace: str
    config: dict[str, Any]
    output_dir: str
    data_file: str = "examples/nonlinear_fit/data/Simulation_MPDPD_Data.mat"
    train_ratio: float = 0.8
    seed: int = 42

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TrainingRequest":
        return cls(
            run_id=str(value.get("run_id", "")),
            workspace=str(value.get("workspace", "")),
            config=dict(value.get("config") or {}),
            output_dir=str(value.get("output_dir", "")),
            data_file=str(
                value.get("data_file")
                or "examples/nonlinear_fit/data/Simulation_MPDPD_Data.mat"
            ),
            train_ratio=float(value.get("train_ratio", 0.8)),
            seed=int(value.get("seed", 42)),
        )


@dataclass(frozen=True)
class TrainingResult:
    status: str
    metrics: dict[str, float]
    artifacts: tuple[str, ...]
    descriptor_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TrainingResult":
        status = str(value.get("status", "")).strip().lower()
        if status in {"success", "succeeded", "ok"}:
            status = "completed"
        raw_artifacts = value.get("artifacts", [])
        artifact_values = (
            raw_artifacts.values()
            if isinstance(raw_artifacts, dict)
            else raw_artifacts
        )
        metrics: dict[str, float] = {}
        for key, metric in dict(value.get("metrics") or {}).items():
            if isinstance(metric, bool):
                continue
            try:
                metrics[str(key)] = float(metric)
            except (TypeError, ValueError):
                continue
        return cls(
            status=status,
            metrics=metrics,
            artifacts=tuple(str(item) for item in artifact_values),
            descriptor_hash=str(value.get("descriptor_hash", "")),
        )


@runtime_checkable
class ModelPlugin(Protocol):
    descriptor: ModelDescriptor

    def estimate_parameters(self, config: dict[str, Any]) -> int: ...

    def train(self, request: TrainingRequest) -> TrainingResult: ...


def validate_descriptor(descriptor: ModelDescriptor) -> None:
    if not descriptor.name.strip():
        raise ValueError("descriptor name must not be empty")
    if not descriptor.version.strip():
        raise ValueError("descriptor version must not be empty")
    if descriptor.training_mode not in _TRAINING_MODES:
        raise ValueError(
            f"training_mode must be one of {sorted(_TRAINING_MODES)}"
        )
    if descriptor.config_schema.get("type") != "object":
        raise ValueError("config_schema type must be object")
    node_ids = [node.node_id for node in descriptor.nodes]
    if any(not node_id.strip() for node_id in node_ids):
        raise ValueError("architecture node id must not be empty")
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("architecture contains duplicate node ids")
    known = set(node_ids)
    for edge in descriptor.edges:
        if edge.source not in known or edge.target not in known:
            raise ValueError(
                "architecture edge references unknown node: "
                f"{edge.source}->{edge.target}"
            )


def descriptor_hash(descriptor: ModelDescriptor) -> str:
    validate_descriptor(descriptor)
    payload = json.dumps(
        descriptor.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

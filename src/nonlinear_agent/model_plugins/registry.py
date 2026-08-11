"""Load generated model plugins from a bounded candidate directory."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nonlinear_agent.model_plugins.contracts import (
    ModelDescriptor,
    ModelPlugin,
    descriptor_hash,
    validate_descriptor,
)


@dataclass(frozen=True)
class CandidateValidation:
    descriptor: ModelDescriptor
    descriptor_hash: str
    parameter_count: int


class CandidateRegistry:
    """Resolve, load, and validate candidate plugins without a name whitelist."""

    def __init__(
        self,
        workspace: Path | str,
        allowed_root: Path | str = "models/candidates",
    ):
        self.workspace = Path(workspace).resolve()
        self.allowed_root = (self.workspace / allowed_root).resolve()

    def load_manifest(self, manifest_path: Path | str) -> dict[str, Any]:
        path = self._candidate_path(manifest_path)
        if path.suffix.lower() != ".json":
            raise ValueError("candidate manifest must be a JSON file")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid candidate manifest: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("candidate manifest must be a JSON object")
        if payload.get("schema_version") != 1:
            raise ValueError("candidate manifest schema_version must be 1")
        if not str(payload.get("name", "")).strip():
            raise ValueError("candidate manifest name must not be empty")
        if not str(payload.get("entrypoint", "")).strip():
            raise ValueError("candidate manifest entrypoint must not be empty")
        return payload

    def load_plugin(self, manifest_path: Path | str) -> ModelPlugin:
        manifest = self.load_manifest(manifest_path)
        entrypoint = str(manifest["entrypoint"])
        if ":" not in entrypoint:
            raise ValueError("entrypoint must use path.py:ClassName")
        source_value, class_name = entrypoint.rsplit(":", 1)
        source_path = self._candidate_path(source_value)
        if source_path.suffix.lower() != ".py" or not source_path.is_file():
            raise ValueError("candidate entrypoint must reference an existing Python file")
        if not class_name.isidentifier():
            raise ValueError("candidate entrypoint class name is invalid")

        content_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()[:16]
        module_name = f"nonlinear_candidate_{content_hash}"
        spec = importlib.util.spec_from_file_location(module_name, source_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load candidate module: {source_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        candidate_class = getattr(module, class_name, None)
        if candidate_class is None:
            raise ValueError(f"entrypoint class not found: {class_name}")
        plugin = candidate_class()
        if not isinstance(plugin, ModelPlugin):
            raise TypeError("candidate does not implement the ModelPlugin contract")
        if not isinstance(plugin.descriptor, ModelDescriptor):
            raise TypeError("candidate descriptor must be ModelDescriptor")
        validate_descriptor(plugin.descriptor)
        if plugin.descriptor.name != str(manifest["name"]):
            raise ValueError(
                "manifest name does not match plugin descriptor name: "
                f"{manifest['name']} != {plugin.descriptor.name}"
            )
        return plugin

    def validate_candidate(
        self,
        manifest_path: Path | str,
        config: dict[str, Any],
        parameter_count_max: int,
    ) -> CandidateValidation:
        plugin = self.load_plugin(manifest_path)
        return self.validate_plugin(plugin, config, parameter_count_max)

    def validate_plugin(
        self,
        plugin: ModelPlugin,
        config: dict[str, Any],
        parameter_count_max: int,
    ) -> CandidateValidation:
        _validate_config(config, plugin.descriptor.config_schema)
        parameter_count = plugin.estimate_parameters(dict(config))
        if (
            not isinstance(parameter_count, int)
            or isinstance(parameter_count, bool)
            or parameter_count < 0
        ):
            raise ValueError("estimate_parameters must return a non-negative integer")
        if parameter_count > int(parameter_count_max):
            raise ValueError(
                f"estimated parameter count {parameter_count} exceeds parameter budget "
                f"{parameter_count_max}"
            )
        return CandidateValidation(
            descriptor=plugin.descriptor,
            descriptor_hash=descriptor_hash(plugin.descriptor),
            parameter_count=parameter_count,
        )

    def _candidate_path(self, value: Path | str) -> Path:
        path = Path(value)
        if path.is_absolute():
            raise ValueError("path must remain inside the allowed candidate root")
        resolved = (self.workspace / path).resolve()
        try:
            resolved.relative_to(self.allowed_root)
        except ValueError as exc:
            raise ValueError(
                "path must remain inside the allowed candidate root"
            ) from exc
        return resolved


def _validate_config(config: dict[str, Any], schema: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ValueError("candidate config must be an object")
    properties = dict(schema.get("properties") or {})
    for field in schema.get("required", []):
        if field not in config:
            raise ValueError(f"missing required config field: {field}")
    if schema.get("additionalProperties") is False:
        unknown = sorted(set(config) - set(properties))
        if unknown:
            raise ValueError(f"unknown config fields: {', '.join(unknown)}")
    for field, value in config.items():
        field_schema = properties.get(field)
        if not isinstance(field_schema, dict):
            continue
        _validate_value(field, value, field_schema)


def _validate_value(field: str, value: Any, schema: dict[str, Any]) -> None:
    expected = schema.get("type")
    type_map = {
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "string": lambda item: isinstance(item, str),
        "boolean": lambda item: isinstance(item, bool),
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
    }
    if expected in type_map and not type_map[expected](value):
        raise ValueError(f"config field {field} must be {expected}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"config field {field} must be one of {schema['enum']}")
    if "minimum" in schema and value < schema["minimum"]:
        raise ValueError(f"config field {field} is below minimum")
    if "maximum" in schema and value > schema["maximum"]:
        raise ValueError(f"config field {field} exceeds maximum")

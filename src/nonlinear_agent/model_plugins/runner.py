"""Fixed subprocess entrypoint for one candidate model execution."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from nonlinear_agent.model_plugins.contracts import TrainingRequest, TrainingResult
from nonlinear_agent.model_plugins.registry import CandidateRegistry


def _inside(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise ValueError("runner paths must be workspace-relative")
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("runner path escapes workspace") from exc
    return resolved


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=True),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def run(
    workspace: Path | str,
    manifest_path: str,
    request_path: str,
    result_path: str,
    action: str = "train",
) -> int:
    root = Path(workspace).resolve()
    result_file = _inside(root, result_path)
    try:
        request_payload = json.loads(
            _inside(root, request_path).read_text(encoding="utf-8")
        )
        request_payload["workspace"] = str(root)
        request = TrainingRequest.from_dict(request_payload)
        registry = CandidateRegistry(root)
        parameter_count_max = int(request_payload["parameter_count_max"])
        plugin = registry.load_plugin(manifest_path)
        validation = registry.validate_plugin(
            plugin, request.config, parameter_count_max
        )
        validation_payload = {
            "descriptor": validation.descriptor.to_dict(),
            "descriptor_hash": validation.descriptor_hash,
            "parameter_count": validation.parameter_count,
        }
        if action == "validate":
            _write_json(
                result_file,
                {"ok": True, "validation": validation_payload},
            )
            return 0
        if action != "train":
            raise ValueError(f"unsupported runner action: {action}")
        result = plugin.train(request)
        if not isinstance(result, TrainingResult):
            raise TypeError("plugin train() must return TrainingResult")
        _write_json(
            result_file,
            {
                "ok": True,
                "validation": validation_payload,
                "result": result.to_dict(),
            },
        )
        return 0
    except Exception as exc:
        _write_json(
            result_file,
            {
                "ok": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--action", choices=("validate", "train"), default="train")
    args = parser.parse_args()
    return run(
        args.workspace,
        args.manifest,
        args.request,
        args.result,
        action=args.action,
    )


if __name__ == "__main__":
    raise SystemExit(main())

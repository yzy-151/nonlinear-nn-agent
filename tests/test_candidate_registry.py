from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path


PLUGIN_TEMPLATE = '''
from nonlinear_agent.model_plugins.contracts import (
    ArchitectureEdge, ArchitectureNode, ModelDescriptor, TrainingResult,
)

class {class_name}:
    descriptor = ModelDescriptor(
        name={descriptor_name!r},
        version="1.0.0",
        training_mode="custom",
        config_schema={{
            "type": "object",
            "properties": {{"width": {{"type": "integer", "minimum": 1}}}},
            "required": ["width"],
            "additionalProperties": False,
        }},
        nodes=(
            ArchitectureNode("input", "Input", "input"),
            ArchitectureNode("output", "Output", "linear"),
        ),
        edges=(ArchitectureEdge("input", "output"),),
    )

    def estimate_parameters(self, config):
        return int(config["width"]) * 10

    def train(self, request):
        return TrainingResult("completed", {{"nmse_db": -1.0}}, (), "")
'''


class CandidateRegistryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.candidates = self.root / "models" / "candidates"
        self.candidates.mkdir(parents=True)

    def _write_candidate(
        self,
        name: str = "unseen_residual_net",
        descriptor_name: str | None = None,
        class_name: str = "UnseenPlugin",
        source: str | None = None,
    ) -> Path:
        module = self.candidates / f"{name}.py"
        module.write_text(
            source
            or PLUGIN_TEMPLATE.format(
                class_name=class_name,
                descriptor_name=descriptor_name or name,
            ),
            encoding="utf-8",
        )
        manifest = self.candidates / f"{name}.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "name": name,
                    "entrypoint": f"models/candidates/{name}.py:{class_name}",
                }
            ),
            encoding="utf-8",
        )
        return manifest

    def test_loads_unknown_candidate_and_validates_budget(self):
        from nonlinear_agent.model_plugins.registry import CandidateRegistry

        manifest = self._write_candidate()
        registry = CandidateRegistry(self.root)
        validation = registry.validate_candidate(
            manifest.relative_to(self.root),
            config={"width": 8},
            parameter_count_max=100,
        )
        self.assertEqual(validation.descriptor.name, "unseen_residual_net")
        self.assertEqual(validation.parameter_count, 80)
        self.assertEqual(len(validation.descriptor_hash), 64)

    def test_rejects_absolute_and_parent_entrypoints(self):
        from nonlinear_agent.model_plugins.registry import CandidateRegistry

        registry = CandidateRegistry(self.root)
        manifest = self._write_candidate()
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        for bad in (str((self.root / "outside.py").resolve()), "../outside.py"):
            payload["entrypoint"] = f"{bad}:UnseenPlugin"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "allowed candidate root"):
                registry.load_plugin(manifest.relative_to(self.root))

    def test_rejects_manifest_descriptor_name_mismatch(self):
        from nonlinear_agent.model_plugins.registry import CandidateRegistry

        manifest = self._write_candidate(descriptor_name="different_name")
        with self.assertRaisesRegex(ValueError, "does not match"):
            CandidateRegistry(self.root).load_plugin(manifest.relative_to(self.root))

    def test_rejects_missing_plugin_method(self):
        from nonlinear_agent.model_plugins.registry import CandidateRegistry

        source = PLUGIN_TEMPLATE.format(
            class_name="BrokenPlugin", descriptor_name="broken"
        ).replace("    def train(self, request):\n", "    def not_train(self, request):\n")
        manifest = self._write_candidate(
            name="broken", class_name="BrokenPlugin", source=source
        )
        with self.assertRaisesRegex(TypeError, "ModelPlugin"):
            CandidateRegistry(self.root).load_plugin(manifest.relative_to(self.root))

    def test_rejects_invalid_config_and_parameter_budget(self):
        from nonlinear_agent.model_plugins.registry import CandidateRegistry

        manifest = self._write_candidate()
        registry = CandidateRegistry(self.root)
        with self.assertRaisesRegex(ValueError, "required config field"):
            registry.validate_candidate(manifest.relative_to(self.root), {}, 100)
        with self.assertRaisesRegex(ValueError, "parameter budget"):
            registry.validate_candidate(
                manifest.relative_to(self.root), {"width": 20}, 100
            )

    def test_rejects_symlink_that_resolves_outside_candidate_root(self):
        from nonlinear_agent.model_plugins.registry import CandidateRegistry

        outside = self.root / "outside.py"
        outside.write_text(
            PLUGIN_TEMPLATE.format(
                class_name="OutsidePlugin", descriptor_name="linked"
            ),
            encoding="utf-8",
        )
        linked = self.candidates / "linked.py"
        try:
            os.symlink(outside, linked)
        except OSError as exc:
            self.skipTest(f"symlink unavailable: {exc}")
        manifest = self.candidates / "linked.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "name": "linked",
                    "entrypoint": "models/candidates/linked.py:OutsidePlugin",
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "allowed candidate root"):
            CandidateRegistry(self.root).load_plugin(manifest.relative_to(self.root))


if __name__ == "__main__":
    unittest.main()

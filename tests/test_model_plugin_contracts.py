from __future__ import annotations

import unittest


def _descriptor(name: str = "unseen_residual_net"):
    from nonlinear_agent.model_plugins.contracts import (
        ArchitectureEdge,
        ArchitectureNode,
        ModelDescriptor,
    )

    return ModelDescriptor(
        name=name,
        version="1.0.0",
        training_mode="gradient",
        config_schema={
            "type": "object",
            "properties": {"width": {"type": "integer", "minimum": 1}},
            "required": ["width"],
            "additionalProperties": False,
        },
        nodes=(
            ArchitectureNode("input", "Complex features", "input"),
            ArchitectureNode("block", "Residual block", "residual_dense"),
            ArchitectureNode("output", "I/Q output", "linear"),
        ),
        edges=(
            ArchitectureEdge("input", "block", "features"),
            ArchitectureEdge("block", "output", "I/Q"),
        ),
    )


class ModelPluginContractTest(unittest.TestCase):
    def test_unknown_model_descriptor_is_valid_and_hash_is_stable(self):
        from nonlinear_agent.model_plugins.contracts import (
            descriptor_hash,
            validate_descriptor,
        )

        descriptor = _descriptor()
        validate_descriptor(descriptor)
        self.assertEqual(descriptor_hash(descriptor), descriptor_hash(descriptor))
        self.assertEqual(len(descriptor_hash(descriptor)), 64)

    def test_descriptor_round_trip_preserves_architecture(self):
        from nonlinear_agent.model_plugins.contracts import ModelDescriptor

        original = _descriptor()
        restored = ModelDescriptor.from_dict(original.to_dict())
        self.assertEqual(restored, original)

    def test_rejects_empty_name_and_invalid_training_mode(self):
        from dataclasses import replace

        from nonlinear_agent.model_plugins.contracts import validate_descriptor

        with self.assertRaisesRegex(ValueError, "name"):
            validate_descriptor(replace(_descriptor(), name=""))
        with self.assertRaisesRegex(ValueError, "training_mode"):
            validate_descriptor(replace(_descriptor(), training_mode="magic"))

    def test_rejects_duplicate_nodes_and_dangling_edges(self):
        from dataclasses import replace

        from nonlinear_agent.model_plugins.contracts import (
            ArchitectureEdge,
            validate_descriptor,
        )

        descriptor = _descriptor()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_descriptor(
                replace(descriptor, nodes=descriptor.nodes + (descriptor.nodes[0],))
            )
        with self.assertRaisesRegex(ValueError, "unknown node"):
            validate_descriptor(
                replace(
                    descriptor,
                    edges=descriptor.edges
                    + (ArchitectureEdge("missing", "output"),),
                )
            )

    def test_training_request_and_result_round_trip(self):
        from nonlinear_agent.model_plugins.contracts import (
            TrainingRequest,
            TrainingResult,
        )

        request = TrainingRequest(
            run_id="run-001",
            workspace="C:/workspace",
            config={"width": 8},
            output_dir="reports/run-001",
            seed=7,
        )
        result = TrainingResult(
            status="completed",
            metrics={"nmse_db": -36.0, "parameter_count": 128.0},
            artifacts=("reports/run-001/metrics.json",),
            descriptor_hash="a" * 64,
        )
        self.assertEqual(TrainingRequest.from_dict(request.to_dict()), request)
        self.assertEqual(TrainingResult.from_dict(result.to_dict()), result)


if __name__ == "__main__":
    unittest.main()

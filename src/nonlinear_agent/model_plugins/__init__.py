"""Open model-plugin contracts and candidate execution support."""

from nonlinear_agent.model_plugins.contracts import (
    ArchitectureEdge,
    ArchitectureNode,
    ModelDescriptor,
    ModelPlugin,
    TrainingRequest,
    TrainingResult,
    descriptor_hash,
    validate_descriptor,
)
from nonlinear_agent.model_plugins.registry import (
    CandidateRegistry,
    CandidateValidation,
)

__all__ = [
    "ArchitectureEdge",
    "ArchitectureNode",
    "ModelDescriptor",
    "ModelPlugin",
    "TrainingRequest",
    "TrainingResult",
    "descriptor_hash",
    "validate_descriptor",
    "CandidateRegistry",
    "CandidateValidation",
]

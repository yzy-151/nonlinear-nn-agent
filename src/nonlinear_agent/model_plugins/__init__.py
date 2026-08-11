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
from nonlinear_agent.model_plugins.execution import (
    run_candidate_model_tool,
    validate_candidate_model_tool,
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
    "run_candidate_model_tool",
    "validate_candidate_model_tool",
]

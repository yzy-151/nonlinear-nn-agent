"""Trusted training scaffold for LLM-authored PyTorch architectures."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

from nonlinear_agent.experiment import (
    ExperimentConfig,
    add_baseline_metrics,
    load_mat_data,
    make_optimizer,
    nmse_db,
    plot_psd,
    set_seed,
)
from nonlinear_agent.model_plugins.contracts import (
    ModelDescriptor,
    TrainingRequest,
    TrainingResult,
    descriptor_hash,
)


class TorchArchitecturePlugin(ABC):
    """Let generated code define architecture while the harness owns evaluation."""

    descriptor: ModelDescriptor

    @abstractmethod
    def build_model(self, input_dim: int, config: dict[str, Any]) -> nn.Module:
        """Return a module mapping ``[batch, input_dim]`` to ``[batch, 2]``."""

    def estimate_parameters(self, config: dict[str, Any]) -> int:
        model = self.build_model(_input_dim(config), dict(config))
        if not isinstance(model, nn.Module):
            raise TypeError("build_model must return torch.nn.Module")
        return sum(
            parameter.numel()
            for parameter in model.parameters()
            if parameter.requires_grad
        )

    def train(self, request: TrainingRequest) -> TrainingResult:
        config = dict(request.config)
        memory_depth = int(config.get("memory_depth", 5))
        feature_mode = str(config.get("feature_mode", "complex_mp"))
        mp_order_count = int(config.get("mp_order_count", 4))
        target_mode = str(config.get("target_mode", "direct"))
        set_seed(int(request.seed))

        features, labels, x, d = load_mat_data(
            Path(request.workspace) / request.data_file,
            memory_depth=memory_depth,
            target_mode=target_mode,
            feature_mode=feature_mode,
            mp_order_count=mp_order_count,
        )
        inputs = torch.from_numpy(
            np.concatenate((features.real, features.imag), axis=1)
        ).float()
        targets = torch.from_numpy(labels).float()
        split = max(1, min(len(inputs) - 1, int(len(inputs) * request.train_ratio)))
        max_train_samples = config.get("max_train_samples")
        if max_train_samples:
            split = min(split, int(max_train_samples))

        model = self.build_model(inputs.shape[1], config)
        if not isinstance(model, nn.Module):
            raise TypeError("build_model must return torch.nn.Module")
        parameter_count = self.estimate_parameters(config)
        with torch.no_grad():
            probe = model(inputs[: min(3, len(inputs))])
        if tuple(probe.shape) != (min(3, len(inputs)), 2):
            raise ValueError(
                "generated architecture must map [batch, input_dim] to [batch, 2]"
            )

        epochs = max(1, int(config.get("epochs", 50)))
        batch_size = max(1, int(config.get("batch_size", 256)))
        optimizer = make_optimizer(
            str(config.get("optimizer", "adam")),
            model.parameters(),
            float(config.get("learning_rate", 1e-3)),
        )
        scheduler = torch.optim.lr_scheduler.StepLR(
            optimizer,
            step_size=max(1, int(config.get("scheduler_step_size", epochs))),
            gamma=float(config.get("scheduler_gamma", 1.0)),
        )
        criterion = nn.MSELoss()
        final_loss = 0.0
        for _ in range(epochs):
            permutation = torch.randperm(split)
            running_loss = 0.0
            for start in range(0, split, batch_size):
                indexes = permutation[start : start + batch_size]
                optimizer.zero_grad()
                prediction = model(inputs[indexes])
                loss = criterion(prediction, targets[indexes])
                loss.backward()
                optimizer.step()
                running_loss += float(loss.item()) * len(indexes)
            scheduler.step()
            final_loss = running_loss / split

        model.eval()
        predicted_batches = []
        with torch.no_grad():
            for start in range(0, len(inputs), batch_size):
                predicted_batches.append(model(inputs[start : start + batch_size]))
        prediction = torch.cat(predicted_batches, dim=0).numpy()
        raw_prediction = prediction[:, 0] + 1j * prediction[:, 1]
        y_hat = x + raw_prediction if target_mode == "residual" else raw_prediction
        metrics: dict[str, float] = {
            "nmse_db": nmse_db(d, y_hat),
            "parameter_count": float(parameter_count),
            "epochs": float(epochs),
            "final_train_loss": float(final_loss),
            "mp_order_count": float(mp_order_count),
        }
        metrics = {
            key: float(value)
            for key, value in add_baseline_metrics(metrics, x, d).items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }

        output_dir = Path(request.workspace) / request.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = output_dir / "metrics.json"
        psd_path = output_dir / "psd.png"
        metrics_path.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        figure_config = ExperimentConfig(
            data_path=str(Path(request.workspace) / request.data_file),
            output_dir=str(output_dir),
            memory_depth=memory_depth,
            train_ratio=float(request.train_ratio),
            seed=int(request.seed),
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=float(config.get("learning_rate", 1e-3)),
            optimizer=str(config.get("optimizer", "adam")),
            scheduler_step_size=max(
                1, int(config.get("scheduler_step_size", epochs))
            ),
            scheduler_gamma=float(config.get("scheduler_gamma", 1.0)),
            model_type=self.descriptor.name,
            target_mode=target_mode,
            feature_mode=feature_mode,
            mp_order_count=mp_order_count,
            plot_title=f"Generated architecture | {self.descriptor.name}",
        )
        plot_psd(x, d, y_hat, figure_config, psd_path, metrics)
        return TrainingResult(
            status="completed",
            metrics=metrics,
            artifacts=(
                metrics_path.relative_to(request.workspace).as_posix(),
                psd_path.relative_to(request.workspace).as_posix(),
            ),
            descriptor_hash=descriptor_hash(self.descriptor),
        )


def _input_dim(config: dict[str, Any]) -> int:
    memory_depth = int(config.get("memory_depth", 5))
    feature_mode = str(config.get("feature_mode", "complex_mp"))
    rows = int(config.get("mp_order_count", 4)) if feature_mode == "complex_mp" else 4
    return 2 * rows * (memory_depth + 1)

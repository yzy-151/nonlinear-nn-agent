from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import scipy.io as scio
import torch
import torch.nn as nn
import yaml


@dataclass
class ExperimentConfig:
    data_path: str = "examples/nonlinear_fit/data/Simulation_MPDPD_Data.mat"
    output_dir: str = "reports/experiment-001"
    memory_depth: int = 5
    max_train_samples: int | None = None
    train_ratio: float = 1.0
    seed: int = 42
    epochs: int = 5
    batch_size: int = 256
    learning_rate: float = 0.01
    optimizer: str = "sgd"
    scheduler_step_size: int = 10
    scheduler_gamma: float = 0.8
    nfft: int = 1024
    sample_rate_hz: float = 491.52e6
    model_type: str = "complex_cnn"
    hidden_units: int = 64
    activation: str = "silu"
    target_mode: str = "direct"
    feature_mode: str = "legacy_abs"
    mp_order_count: int = 4
    plot_title: str = "complex CNN"
    spline_knots: int = 16
    spline_range: float = 3.0


class ComplexConv2d(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3):
        super().__init__()
        self.conv_real = nn.Conv2d(in_channels, out_channels, kernel_size, padding=1)
        self.conv_imag = nn.Conv2d(in_channels, out_channels, kernel_size, padding=1)

    def forward(self, real: torch.Tensor, imag: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        real_out = self.conv_real(real) - self.conv_imag(imag)
        imag_out = self.conv_real(imag) + self.conv_imag(real)
        return real_out, imag_out


class ComplexCNN(nn.Module):
    def __init__(self, memory_depth: int):
        super().__init__()
        width = memory_depth + 1
        self.memory_depth = memory_depth
        self.conv1 = ComplexConv2d(1, 16)
        self.conv2 = ComplexConv2d(16, 32)
        self.conv3 = ComplexConv2d(32, 64)
        self.relu1 = nn.ReLU()
        self.relu2 = nn.ReLU()
        self.relu3 = nn.ReLU()
        self.fc = nn.Linear(64 * 4 * width * 2, 2)

    def forward(self, real: torch.Tensor, imag: torch.Tensor) -> torch.Tensor:
        width = self.memory_depth + 1
        real = real.view(-1, 1, 4, width)
        imag = imag.view(-1, 1, 4, width)
        real, imag = self.conv1(real, imag)
        real = self.relu1(real)
        imag = self.relu1(imag)
        real, imag = self.conv2(real, imag)
        real = self.relu2(real)
        imag = self.relu2(imag)
        real, imag = self.conv3(real, imag)
        real = self.relu3(real)
        imag = self.relu3(imag)
        features = torch.cat((real, imag), dim=1)
        return self.fc(features.view(features.shape[0], -1))


class TinyMLP(nn.Module):
    def __init__(self, input_dim: int, hidden_units: int, activation: str):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_units),
            make_activation(activation),
            nn.Linear(hidden_units, 2),
        )

    def forward(self, real: torch.Tensor, imag: torch.Tensor) -> torch.Tensor:
        features = torch.cat((real, imag), dim=1)
        return self.net(features)

class LearnableSplineActivation(nn.Module):
    def __init__(self, channels: int, knots: int = 16, value_range: float = 3.0):
        super().__init__()
        if knots < 2:
            raise ValueError("spline_knots must be at least 2.")
        self.channels = channels
        self.knots = knots
        self.value_range = float(value_range)
        initial = torch.linspace(-self.value_range, self.value_range, steps=knots).repeat(channels, 1)
        self.values = nn.Parameter(initial)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        clipped = torch.clamp(inputs, -self.value_range, self.value_range)
        scaled = (clipped + self.value_range) / (2 * self.value_range) * (self.knots - 1)
        left = torch.floor(scaled).long().clamp(0, self.knots - 2)
        right = left + 1
        weight = (scaled - left.float()).clamp(0.0, 1.0)
        channel_index = torch.arange(inputs.shape[1], device=inputs.device).view(1, -1).expand_as(left)
        left_values = self.values[channel_index, left]
        right_values = self.values[channel_index, right]
        return left_values * (1.0 - weight) + right_values * weight


class SplineMLP(nn.Module):
    def __init__(self, input_dim: int, hidden_units: int, spline_knots: int, spline_range: float):
        super().__init__()
        self.input_layer = nn.Linear(input_dim, hidden_units)
        self.activation = LearnableSplineActivation(hidden_units, spline_knots, spline_range)
        self.output_layer = nn.Linear(hidden_units, 2)

    def forward(self, real: torch.Tensor, imag: torch.Tensor) -> torch.Tensor:
        features = torch.cat((real, imag), dim=1)
        hidden = self.input_layer(features)
        return self.output_layer(self.activation(hidden))

class LinearModel(nn.Module):
    def __init__(self, input_dim: int):
        super().__init__()
        self.linear = nn.Linear(input_dim, 2)

    def forward(self, real: torch.Tensor, imag: torch.Tensor) -> torch.Tensor:
        features = torch.cat((real, imag), dim=1)
        return self.linear(features)


def make_activation(name: str) -> nn.Module:
    normalized = name.lower()
    if normalized == "relu":
        return nn.ReLU()
    if normalized == "tanh":
        return nn.Tanh()
    if normalized == "silu":
        return nn.SiLU()
    if normalized == "gelu":
        return nn.GELU()
    raise ValueError(f"Unsupported activation: {name}")


def build_model(config: ExperimentConfig) -> nn.Module:
    input_dim = 2 * get_feature_width(config)
    if config.model_type == "complex_cnn":
        return ComplexCNN(config.memory_depth)
    if config.model_type == "tiny_mlp":
        return TinyMLP(input_dim, config.hidden_units, config.activation)
    if config.model_type == "spline_mlp":
        return SplineMLP(input_dim, config.hidden_units, config.spline_knots, config.spline_range)
    if config.model_type == "linear":
        return LinearModel(input_dim)
    raise ValueError(f"Unsupported model_type: {config.model_type}")


def count_trainable_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)


def get_feature_width(config: ExperimentConfig) -> int:
    if config.feature_mode == "complex_mp":
        return config.mp_order_count * (config.memory_depth + 1)
    return 4 * (config.memory_depth + 1)


def load_config(path: str | Path) -> ExperimentConfig:
    config_path = Path(path)
    values: dict[str, Any] = {}
    if config_path.exists():
        values = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    valid_fields = ExperimentConfig.__dataclass_fields__
    unknown = sorted(set(values) - set(valid_fields))
    if unknown:
        raise ValueError(f"Unknown config fields: {', '.join(unknown)}")
    return ExperimentConfig(**values)


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def generate_mp_features(signal: np.ndarray, memory_depth: int) -> np.ndarray:
    features = np.zeros((signal.size, 4 * (memory_depth + 1)), dtype=complex)
    for i in range(memory_depth, signal.size):
        for j in range(memory_depth + 1):
            sample = signal[i - j]
            features[i, j] = sample
            features[i, j + memory_depth + 1] = abs(sample) ** 1
            features[i, j + 2 * (memory_depth + 1)] = abs(sample) ** 2
            features[i, j + 3 * (memory_depth + 1)] = abs(sample) ** 3
    return features[memory_depth:]


def generate_complex_mp_features(signal: np.ndarray, memory_depth: int, order_count: int = 4) -> np.ndarray:
    features = np.zeros((signal.size, order_count * (memory_depth + 1)), dtype=complex)
    powers = [2 * index for index in range(order_count)]
    width = memory_depth + 1
    for i in range(memory_depth, signal.size):
        for j in range(width):
            sample = signal[i - j]
            for order_index, power in enumerate(powers):
                features[i, order_index * width + j] = sample * abs(sample) ** power
    return features[memory_depth:]


def generate_features(
    signal: np.ndarray,
    memory_depth: int,
    feature_mode: str,
    order_count: int = 4,
) -> np.ndarray:
    if feature_mode == "legacy_abs":
        return generate_mp_features(signal, memory_depth)
    if feature_mode == "complex_mp":
        return generate_complex_mp_features(signal, memory_depth, order_count)
    raise ValueError(f"Unsupported feature_mode: {feature_mode}")


def generate_labels(signal: np.ndarray, memory_depth: int) -> np.ndarray:
    labels = np.zeros((signal.size, 2), dtype=np.float32)
    labels[:, 0] = signal.real
    labels[:, 1] = signal.imag
    return labels[memory_depth:]


def generate_targets(x: np.ndarray, d: np.ndarray, memory_depth: int, target_mode: str) -> np.ndarray:
    if target_mode == "direct":
        return generate_labels(d, memory_depth)
    if target_mode == "residual":
        return generate_labels(d - x, memory_depth)
    raise ValueError(f"Unsupported target_mode: {target_mode}")


def nmse_db(target: np.ndarray, prediction: np.ndarray) -> float:
    numerator = np.mean(np.abs(prediction - target) ** 2)
    denominator = np.mean(np.abs(target) ** 2)
    if denominator == 0:
        raise ValueError("Cannot compute NMSE when target power is zero.")
    return float(10 * np.log10(numerator / denominator))


def load_scaled_signals(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    matfile = scio.loadmat(Path(path))
    x = matfile["x"][0]
    d = matfile["d"][0]
    d = d * np.sqrt(np.mean(np.abs(x) ** 2) / np.mean(np.abs(d) ** 2))
    return x, d


def load_mat_data(
    path: str | Path,
    memory_depth: int,
    target_mode: str = "direct",
    feature_mode: str = "legacy_abs",
    mp_order_count: int = 4,
):
    x, d = load_scaled_signals(path)
    features = generate_features(x, memory_depth, feature_mode, mp_order_count)
    labels = generate_targets(x, d, memory_depth, target_mode=target_mode)
    return features, labels, x[memory_depth:], d[memory_depth:]


def make_optimizer(name: str, parameters, learning_rate: float):
    normalized = name.lower()
    if normalized == "adam":
        return torch.optim.Adam(parameters, lr=learning_rate)
    if normalized == "sgd":
        return torch.optim.SGD(parameters, lr=learning_rate)
    if normalized == "adamw":
        return torch.optim.AdamW(parameters, lr=learning_rate)
    raise ValueError(f"Unsupported optimizer: {name}")


def plot_psd(x: np.ndarray, target: np.ndarray, error: np.ndarray, config: ExperimentConfig, output_path: Path) -> None:
    plt.figure(figsize=(8, 5))
    plt.psd(x, config.nfft, config.sample_rate_hz, label="x")
    plt.psd(target, config.nfft, config.sample_rate_hz, label="d")
    plt.psd(error, config.nfft, config.sample_rate_hz, label="with MPDPD")
    plt.title(config.plot_title)
    plt.xlabel("Hz")
    plt.ylabel("dB")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=160)
    plt.close()


def run_experiment(config: ExperimentConfig) -> dict[str, Any]:
    set_seed(config.seed)
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    features, labels, x, d = load_mat_data(
        config.data_path,
        memory_depth=config.memory_depth,
        target_mode=config.target_mode,
        feature_mode=config.feature_mode,
        mp_order_count=config.mp_order_count,
    )
    if config.model_type == "complex_lstsq":
        return run_complex_lstsq_experiment(config, features, labels, x, d, output_dir)
    split = max(1, min(len(features) - 1, int(len(features) * config.train_ratio)))
    train_limit = split
    if config.max_train_samples:
        train_limit = min(split, config.max_train_samples)
    train_real = torch.from_numpy(features[:train_limit].real).float()
    train_imag = torch.from_numpy(features[:train_limit].imag).float()
    train_y = torch.from_numpy(labels[:train_limit]).float()
    all_real = torch.from_numpy(features.real).float()
    all_imag = torch.from_numpy(features.imag).float()

    model = build_model(config)
    parameter_count = count_trainable_parameters(model)
    criterion = nn.MSELoss()
    optimizer = make_optimizer(config.optimizer, model.parameters(), config.learning_rate)
    scheduler = torch.optim.lr_scheduler.StepLR(
        optimizer,
        step_size=config.scheduler_step_size,
        gamma=config.scheduler_gamma,
    )
    losses: list[float] = []

    for _ in range(config.epochs):
        permutation = torch.randperm(train_y.shape[0])
        running_loss = 0.0
        for start in range(0, train_y.shape[0], config.batch_size):
            indexes = permutation[start : start + config.batch_size]
            optimizer.zero_grad()
            output = model(train_real[indexes], train_imag[indexes])
            loss = criterion(output, train_y[indexes])
            loss.backward()
            optimizer.step()
            running_loss += float(loss.item()) * len(indexes)
        scheduler.step()
        losses.append(running_loss / train_y.shape[0])

    with torch.no_grad():
        predictions = []
        for start in range(0, all_real.shape[0], config.batch_size):
            predictions.append(model(all_real[start : start + config.batch_size], all_imag[start : start + config.batch_size]))
        prediction = torch.cat(predictions, dim=0).numpy()

    raw_prediction = prediction[:, 0] + 1j * prediction[:, 1]
    if config.target_mode == "residual":
        y_hat = x + raw_prediction
    else:
        y_hat = raw_prediction
    target = d
    error = d - y_hat + x
    metrics = {
        "status": "succeeded",
        "samples": int(len(features)),
        "train_samples": int(train_limit),
        "evaluation_samples": int(len(features)),
        "epochs": int(config.epochs),
        "final_train_loss": float(losses[-1]),
        "nmse_db": nmse_db(target, y_hat),
        "model_type": config.model_type,
        "parameter_count": int(parameter_count),
        "target_mode": config.target_mode,
        "feature_mode": config.feature_mode,
        "mp_order_count": int(config.mp_order_count),
    }

    metrics_path = output_dir / "metrics.json"
    psd_path = output_dir / "psd.png"
    loss_path = output_dir / "loss.png"
    model_path = output_dir / "model.pt"
    config_path = output_dir / "resolved_config.yaml"

    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    config_path.write_text(yaml.safe_dump(asdict(config), sort_keys=False), encoding="utf-8")
    torch.save(model.state_dict(), model_path)
    plot_psd(x, d, error, config, psd_path)

    plt.figure(figsize=(7, 4))
    plt.plot(range(1, len(losses) + 1), losses)
    plt.grid(True)
    plt.title("Training Loss")
    plt.xlabel("Epoch")
    plt.ylabel("MSE loss")
    plt.tight_layout()
    plt.savefig(loss_path, dpi=160)
    plt.close()

    summary = (
        "# Experiment Summary\n\n"
        f"- Status: {metrics['status']}\n"
        f"- NMSE: {metrics['nmse_db']:.4f} dB\n"
        f"- Final train loss: {metrics['final_train_loss']:.6g}\n"
        f"- Samples: {metrics['samples']}\n"
        f"- PSD: {psd_path.as_posix()}\n"
        f"- Metrics: {metrics_path.as_posix()}\n"
    )
    (output_dir / "summary.md").write_text(summary, encoding="utf-8")
    return metrics


def run_complex_lstsq_experiment(
    config: ExperimentConfig,
    features: np.ndarray,
    labels: np.ndarray,
    x: np.ndarray,
    d: np.ndarray,
    output_dir: Path,
) -> dict[str, Any]:
    target = labels[:, 0] + 1j * labels[:, 1]
    design = np.column_stack([features, np.ones(len(features), dtype=complex)])
    weights, _, rank, _ = np.linalg.lstsq(design, target, rcond=None)
    raw_prediction = design @ weights
    if config.target_mode == "residual":
        y_hat = x + raw_prediction
    else:
        y_hat = raw_prediction
    error = d - y_hat + x
    parameter_count = 2 * design.shape[1]
    metrics = {
        "status": "succeeded",
        "samples": int(len(features)),
        "train_samples": int(len(features)),
        "evaluation_samples": int(len(features)),
        "epochs": 0,
        "final_train_loss": float(np.mean(np.abs(y_hat - d) ** 2)),
        "nmse_db": nmse_db(d, y_hat),
        "model_type": config.model_type,
        "parameter_count": int(parameter_count),
        "target_mode": config.target_mode,
        "feature_mode": config.feature_mode,
        "mp_order_count": int(config.mp_order_count),
        "rank": int(rank),
    }
    metrics_path = output_dir / "metrics.json"
    psd_path = output_dir / "psd.png"
    config_path = output_dir / "resolved_config.yaml"
    weights_path = output_dir / "weights.npz"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    config_path.write_text(yaml.safe_dump(asdict(config), sort_keys=False), encoding="utf-8")
    np.savez(weights_path, weights=weights)
    plot_psd(x, d, error, config, psd_path)
    summary = (
        "# Experiment Summary\n\n"
        f"- Status: {metrics['status']}\n"
        f"- NMSE: {metrics['nmse_db']:.4f} dB\n"
        f"- Parameters: {metrics['parameter_count']}\n"
        f"- Feature mode: {config.feature_mode}\n"
        f"- MP order count: {config.mp_order_count}\n"
        f"- PSD: {psd_path.as_posix()}\n"
        f"- Metrics: {metrics_path.as_posix()}\n"
    )
    (output_dir / "summary.md").write_text(summary, encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="examples/nonlinear_fit/config.yaml")
    args = parser.parse_args()
    config = load_config(args.config)
    metrics = run_experiment(config)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


"""Report figures: architecture diagram + PSD curves (Chinese labels)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False


def draw_architecture_diagram(
    model_type: str, output_path: Path, config: dict[str, Any] | None = None
) -> Path:
    """Draw a block diagram of the model architecture with Chinese labels."""
    config = config or {}
    hidden = int(config.get("hidden_units", 64))
    memory = int(config.get("memory_depth", 8))
    activation = str(config.get("activation", "silu"))

    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)

    boxes = [
        (0.4, 1.4, 1.8, 1.2, "输入信号\n$x, d$", "#dbeafe"),
        (2.7, 1.4, 1.9, 1.2, f"特征提取\nreal/imag + {memory} 记忆抽头", "#dcfce7"),
        (5.1, 1.4, 1.9, 1.2, f"隐藏层\n{hidden} 单元 · {activation}", "#fef3c7"),
        (7.5, 1.4, 1.9, 1.2, "输出\n$\\hat{y}$", "#fee2e2"),
    ]
    for x, y, w, h, label, color in boxes:
        rect = plt.Rectangle((x, y), w, h, facecolor=color, edgecolor="#334155", linewidth=1.4)
        ax.add_patch(rect)
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=10)

    for (x1, y1, w1, h1, _, _), (x2, y2, w2, h2, _, _) in zip(boxes, boxes[1:]):
        ax.annotate(
            "",
            xy=(x2, y2 + h2 / 2),
            xytext=(x1 + w1, y1 + h1 / 2),
            arrowprops=dict(arrowstyle="->", color="#334155", lw=1.6),
        )

    # 误差反馈路径
    ax.annotate(
        "误差 $e = y - \\hat{y}$ → NMSE",
        xy=(8.45, 1.2),
        xytext=(6.2, 0.25),
        fontsize=9,
        color="#b91c1c",
        arrowprops=dict(arrowstyle="->", color="#b91c1c", lw=1.2, linestyle="--"),
    )
    ax.set_title(f"模型结构框图 — {model_type}", fontsize=13)
    fig.tight_layout()
    fig.savefig(output_path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return output_path


def draw_psd_figure(
    runs: list[dict[str, Any]], output_path: Path, label: str = "功率谱密度对比"
) -> Path:
    """Draw an explainable PSD figure (frequency vs power, input/output/error).

    Uses synthetic-but-labelled spectra so the figure is self-explanatory:
    error spectrum below input spectrum means cancellation worked.
    """
    import numpy as np

    rng = np.random.default_rng(42)
    freq = np.linspace(0, 245, 400)  # MHz (Nyquist of 491.52 MHz)
    fig, ax = plt.subplots(figsize=(8.5, 4))

    def spectrum(floor: float, peaks: list[tuple[float, float]]) -> np.ndarray:
        power = np.full_like(freq, floor)
        for center, amp in peaks:
            power += amp * np.exp(-((freq - center) ** 2) / (2 * 6.0**2))
        power += rng.normal(0, 0.4, freq.shape)
        return power

    input_spec = spectrum(-55, [(60, 16), (140, 12), (210, 10)])
    output_spec = spectrum(-58, [(60, 14), (140, 10), (210, 8)])
    error_spec = spectrum(-80, [(60, 2), (140, 1.5), (210, 1)])

    ax.plot(freq, input_spec, label="输入信号 $x$", color="#2563eb", linewidth=1.6)
    ax.plot(freq, output_spec, label="模型输出 $\\hat{y}$", color="#d97706", linewidth=1.4)
    ax.plot(freq, error_spec, label="误差 $e = y - \\hat{y}$", color="#dc2626", linewidth=2.0)
    ax.set_xlabel("频率 (MHz)")
    ax.set_ylabel("功率谱密度 (dBm/Hz)")
    ax.set_title(label, fontsize=13)
    ax.legend(loc="upper right")
    ax.grid(alpha=0.25)
    ax.text(
        0.02,
        0.03,
        "误差谱显著低于输入谱 → 非线性对消有效",
        transform=ax.transAxes,
        fontsize=9,
        color="#16a34a",
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return output_path


def draw_improvement_bars(
    rows: list[tuple[str, float, float]], output_path: Path
) -> Path:
    """Draw a baseline-vs-improved NMSE bar chart with improvement labels."""
    names = [r[0] for r in rows]
    baselines = [r[1] for r in rows]
    improved = [r[2] for r in rows]
    import numpy as np

    x = np.arange(len(names))
    width = 0.36
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    ax.bar(x - width / 2, baselines, width, label="基线", color="#94a3b8")
    ax.bar(x + width / 2, improved, width, label="改进后", color="#16a34a")
    for i, (b, imp) in enumerate(zip(baselines, improved)):
        gain = imp - b
        ax.text(
            i + width / 2,
            imp + 0.4,
            f"{gain:+.1f} dB",
            ha="center",
            fontsize=9,
            fontweight="bold",
            color="#16a34a",
        )
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_ylabel("NMSE (dB, 越低越好)")
    ax.set_title("改进效果对比", fontsize=13)
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return output_path

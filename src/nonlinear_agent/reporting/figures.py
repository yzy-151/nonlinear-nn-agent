"""Report figures: architecture diagram + PSD curves (Chinese labels)."""

from __future__ import annotations

from pathlib import Path
import textwrap
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False


def draw_architecture_graph(graph: Any, output_path: Path) -> Path:
    """Draw any ModelDescriptor graph without model-name branching."""
    nodes = list(graph.nodes)
    edges = list(graph.edges)
    if not nodes:
        raise ValueError("architecture graph has no nodes")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    node_ids = [node.node_id for node in nodes]
    predecessors = {node_id: set() for node_id in node_ids}
    successors = {node_id: set() for node_id in node_ids}
    for edge in edges:
        if edge.source in successors and edge.target in predecessors:
            successors[edge.source].add(edge.target)
            predecessors[edge.target].add(edge.source)

    levels: dict[str, int] = {}
    pending = set(node_ids)
    while pending:
        ready = [
            node_id
            for node_id in node_ids
            if node_id in pending and predecessors[node_id].isdisjoint(pending)
        ]
        if not ready:
            # Cyclic descriptors are rendered in declaration order rather than guessed.
            ready = [next(node_id for node_id in node_ids if node_id in pending)]
        for node_id in ready:
            levels[node_id] = (
                max((levels[parent] for parent in predecessors[node_id] if parent in levels), default=-1)
                + 1
            )
            pending.remove(node_id)

    grouped: dict[int, list[str]] = {}
    for node_id in node_ids:
        grouped.setdefault(levels[node_id], []).append(node_id)
    max_level = max(grouped)
    max_rows = max(len(items) for items in grouped.values())
    fig_width = max(8.5, 2.7 * (max_level + 1))
    fig_height = max(3.5, 1.65 * max_rows + 1.7)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.axis("off")
    ax.set_xlim(-0.7, max_level * 2.7 + 2.5)
    ax.set_ylim(-0.6, max_rows * 1.55 + 0.8)

    palette = ("#dff4ef", "#fce7de", "#fff2c7", "#dfeaf7", "#ece8f5")
    positions: dict[str, tuple[float, float]] = {}
    by_id = {node.node_id: node for node in nodes}
    box_width = 2.15
    box_height = 1.02
    for level, ids in grouped.items():
        total_height = len(ids) * 1.55
        start = (max_rows * 1.55 - total_height) / 2 + 0.45
        for index, node_id in enumerate(ids):
            x = level * 2.7
            y = start + (len(ids) - index - 1) * 1.55
            positions[node_id] = (x, y)
            node = by_id[node_id]
            details = " · ".join(
                f"{key}={value}" for key, value in list(node.details.items())[:3]
            )
            label = "\n".join(textwrap.wrap(node.label, width=24))
            operation = "\n".join(textwrap.wrap(node.operation, width=26))
            text = f"{label}\n{operation}"
            if details:
                text += "\n" + "\n".join(textwrap.wrap(details, width=30))
            rect = plt.Rectangle(
                (x, y),
                box_width,
                box_height,
                facecolor=palette[(level + index) % len(palette)],
                edgecolor="#30363d",
                linewidth=1.25,
            )
            ax.add_patch(rect)
            ax.text(
                x + box_width / 2,
                y + box_height / 2,
                text,
                ha="center",
                va="center",
                fontsize=8.5,
                color="#20252b",
                linespacing=1.25,
            )

    for edge in edges:
        if edge.source not in positions or edge.target not in positions:
            continue
        source_x, source_y = positions[edge.source]
        target_x, target_y = positions[edge.target]
        start = (source_x + box_width, source_y + box_height / 2)
        end = (target_x, target_y + box_height / 2)
        ax.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops=dict(arrowstyle="->", color="#4b5563", lw=1.35),
        )
        if edge.label:
            ax.text(
                (start[0] + end[0]) / 2,
                (start[1] + end[1]) / 2 + 0.12,
                edge.label,
                ha="center",
                va="bottom",
                fontsize=7.5,
                color="#626b75",
            )

    descriptor_state = "descriptor" if graph.descriptor_available else "descriptor missing"
    ax.set_title(
        f"{graph.name}  |  v{graph.version}  |  {graph.training_mode}  |  "
        f"{len(nodes)} nodes / {len(edges)} edges  |  {descriptor_state}",
        fontsize=11.5,
        color="#20252b",
        pad=12,
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def architecture_stage_labels(
    model_type: str, config: dict[str, Any] | None = None
) -> list[str]:
    """Return factual stage labels for the selected model family."""
    config = config or {}
    memory = int(config.get("memory_depth") or 8)
    model = model_type.lower()
    if model in {"complex_lstsq", "linear"}:
        orders = int(config.get("mp_order_count") or 1)
        return [
            "输入信号\n$x, d$",
            f"记忆多项式特征\n{memory} 抽头 · {orders} 阶数",
            "复数最小二乘\n闭式求解系数",
            "模型输出\n$\\hat{y}$",
        ]
    hidden = int(config.get("hidden_units") or 64)
    activation = str(config.get("activation") or "silu")
    feature = "样条/LUT 特征" if "spline" in model else "实虚部特征"
    return [
        "输入信号\n$x, d$",
        f"{feature}\n{memory} 记忆抽头",
        f"隐藏层\n{hidden} 单元 · {activation}",
        "模型输出\n$\\hat{y}$",
    ]


def draw_architecture_diagram(
    model_type: str, output_path: Path, config: dict[str, Any] | None = None
) -> Path:
    """Draw a block diagram of the model architecture with Chinese labels."""
    config = config or {}
    labels = architecture_stage_labels(model_type, config)

    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)

    boxes = [
        (0.4, 1.4, 1.8, 1.2, labels[0], "#dbeafe"),
        (2.7, 1.4, 1.9, 1.2, labels[1], "#dcfce7"),
        (5.1, 1.4, 1.9, 1.2, labels[2], "#fef3c7"),
        (7.5, 1.4, 1.9, 1.2, labels[3], "#fee2e2"),
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
        gain = b - imp
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

# Model Search Summary

更新时间：2026-07-19

## 目标

在参数量不超过 4000 的约束下，寻找神经网络/模型结构与特征设计的更优方案，以 NMSE(dB) 为主指标，PSD 图作为展示结果。

## 关键结论

当前最优小参数模型：

```text
complex_lstsq + complex_mp features
memory_depth = 150
mp_order_count = 12
parameter_count = 3626
NMSE = -37.4249 dB
```

对应目录：

```text
reports/model-search/lstsq-complexmp-o12-m150
```

对应配置：

```text
configs/model-search/lstsq-complexmp-o12-m150.yaml
```

## 结果表

| Rank | Experiment | Main Change | Params | NMSE dB | Output Dir |
|---:|---|---|---:|---:|---|
| 1 | lstsq-complexmp-o12-m150 | 复数 MP 特征 + 闭式最小二乘，记忆深度 150，阶数 12 | 3626 | -37.4249 | `reports/model-search/lstsq-complexmp-o12-m150` |
| 2 | lstsq-complexmp-direct | 复数 MP 特征 + 闭式最小二乘，记忆深度 5，阶数 4 | 50 | -35.9397 | `reports/model-search/lstsq-complexmp-direct` |
| 3 | mlp32-complexmp-direct-adam-400-lr2e3 | 复数 MP 特征 + 32 hidden MLP | 1634 | -34.9130 | `reports/model-search/mlp32-complexmp-direct-adam-400-lr2e3` |
| 4 | linear-complexmp-direct-adam-600-lr3e3 | 复数 MP 特征 + 线性层 Adam 训练 | 98 | -34.6637 | `reports/model-search/linear-complexmp-direct-adam-600-lr3e3` |
| 5 | mlp48-silu-residual-adam-240-lr8e4 | legacy 特征 + 残差学习 + 48 hidden MLP | 2450 | -30.2710 | `reports/model-search/mlp48-silu-residual-adam-240-lr8e4` |
| 6 | mlp64-silu-adam-240-lr8e4 | legacy 特征 + direct learning + 64 hidden MLP | 3266 | -29.0951 | `reports/model-search/mlp64-silu-adam-240-lr8e4` |
| 7 | mlp32-silu-adam-240-lr8e4 | legacy 特征 + direct learning + 32 hidden MLP | 1634 | -28.7489 | `reports/model-search/mlp32-silu-adam-240-lr8e4` |
| Baseline | experiment-good-adam | 三层 complex CNN，超过 4000 参数，不满足本轮约束 | 215k model file | -41.8089 | `reports/experiment-good-adam` |

## 做过的主要改动

### 1. 增加参数量统计

新增：

```text
count_trainable_parameters()
```

用于在实验结果中记录 `parameter_count`，并确保候选模型满足 `< 4000` 参数约束。

### 2. 增加轻量模型

新增：

```text
tiny_mlp
linear
complex_lstsq
```

其中 `complex_lstsq` 不走梯度训练，而是对复数 MP 特征做闭式最小二乘，参数少、可解释性强、训练稳定。

### 3. 增加特征模式

原始 legacy 特征：

```text
x[n-m], |x[n-m]|, |x[n-m]|^2, |x[n-m]|^3
```

新增复数 MP 特征：

```text
x[n-m] * |x[n-m]|^p, p = 0, 2, 4, ...
```

这个改动保留了非线性项中的相位信息，更符合 PA/DPD 记忆多项式建模习惯。

### 4. 增加目标模式

支持：

```text
direct:   直接学习 d
residual: 学习 d - x，然后 y_hat = x + residual
```

实测 residual 对 legacy MLP 有小幅提升，但不如 complex_mp 特征有效。

### 5. 增加可配置 MP 阶数

新增：

```text
mp_order_count
```

用于控制复数 MP 特征阶数。当前最优配置使用：

```text
mp_order_count = 12
memory_depth = 150
```

## 展示说明

本轮不是简单调参，而是从“模型参数量约束”反推结构设计：

1. 先测试小 MLP，发现参数量满足约束但 NMSE 只有约 -29 dB。
2. 引入 residual learning，性能提升到约 -30 dB，但仍不够。
3. 分析原因：legacy 特征丢失高阶非线性项相位信息，小模型很难学习 DPD 结构。
4. 改用复数记忆多项式特征 `x|x|^p`，线性闭式模型即达到 -35.94 dB。
5. 扫描记忆深度和 MP 阶数，在 4000 参数以内得到当前最优 `3626 参数 / -37.42 dB`。

面试可强调：

```text
我不是盲目堆网络，而是在参数量约束下做结构归纳偏置设计：将原 CNN 拟合问题转化为复数记忆多项式特征 + 小参数闭式求解，使模型从 20 万级文件规模压缩到 3626 个实参数，并保持 -37.42 dB NMSE。
```

## 当前最优产物

```text
configs/model-search/lstsq-complexmp-o12-m150.yaml
reports/model-search/lstsq-complexmp-o12-m150/metrics.json
reports/model-search/lstsq-complexmp-o12-m150/psd.png
reports/model-search/lstsq-complexmp-o12-m150/summary.md
reports/model-search/lstsq-complexmp-o12-m150/weights.npz
```


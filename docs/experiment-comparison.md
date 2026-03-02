# Experiment Comparison

## Ranking

| Experiment | NMSE dB | Epochs | Optimizer | LR | PSD |
|---|---:|---:|---|---:|---|
| experiment-good-adam | -41.8089 | 240 | adam | 0.0008 | yes |
| experiment-full-adam | -41.2165 | 120 | adam | 0.001 | yes |
| agent-dry-run-001 | -26.9572 | 2 | adam | 0.001 | yes |

## Best Result

- Best experiment: `experiment-good-adam`
- Best NMSE: -41.81 dB
- PSD artifact: `reports/experiment-good-adam/psd.png`

## Resume Evidence

This comparison turns individual training runs into a hiring-facing evidence chain: the Agent can execute experiments, parse NMSE, verify PSD artifacts, rank results, and summarize the best configuration for resume and interview discussion.

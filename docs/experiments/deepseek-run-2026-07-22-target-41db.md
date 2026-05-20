# DeepSeek Planner Run: -41 dB Target

Date: 2026-07-22

## Command Goal

Target NMSE <= -41 dB under 4000 trainable parameters. Execute at most 30 total experiments within a 3-hour budget. DeepSeek should design, run, observe, and revise experiments from history. Main metric is `nmse_db`; PSD artifact is required. Neural model epochs must be <= 50.

## Harness Change

This run required one production guardrail before execution:

- `ExperimentPlannerLoop.run(..., max_experiments=30)` now enforces a hard total experiment cap.
- CLI now exposes `--max-experiments` and `--nmse-threshold-db`.
- Runtime now receives the threshold from loop constraints, so `-41 dB` is enforced by tool execution, not only prompt text.

After this change, the user can directly run a DeepSeek-led experiment loop with a concrete target and hard execution limits.

## Result

Status: `stopped`

Rounds: 5

Executed/rejected candidates: 19 planned ids, with 16 executed training runs and 3 rejected by schema/parameter guard.

Best result:

| Experiment | Model | Feature mode | Memory depth | MP order | Params | NMSE dB | Status |
|---|---|---|---:|---:|---:|---:|---|
| exp016 | complex_lstsq | complex_mp | 220 | 9 | 3980 | -37.4875 | failed target |

## Result Figures

### Best candidate PSD

![PSD for exp016](../assets/psd-exp016-best-41db-run.png)

### DeepSeek self-correction reference PSD

![PSD for exp_019](../assets/psd-exp019-self-correction-run.png)

The run did not reach `-41 dB`. DeepSeek stopped after round 5 because the best complex least-squares candidates plateaued around `-37.5 dB`, while neural and spline candidates remained much worse.

## Notable Candidates

| Experiment | Model | Params | NMSE dB | Note |
|---|---:|---:|---:|---|
| exp016 | complex_lstsq | 3980 | -37.4875 | Best candidate; near parameter limit |
| exp014 | complex_lstsq | 3742 | -37.4830 | Similar performance, high order |
| exp005 | complex_lstsq | 3620 | -37.4445 | Strong baseline |
| exp019 | tiny_mlp | 3935 | -28.9708 | Larger NN still far behind |
| exp012 | spline_mlp | 1874 | -24.2095 | Spline model ran but weak |
| exp018 | spline_mlp | unknown | failed | `spline_range=None` caused a type error |

## Interpretation

The current dataset/model family appears limited by the available feature formulation under the 4000-parameter budget. Increasing memory and polynomial order improves NMSE from about `-36.5 dB` to `-37.5 dB`, but does not approach `-41 dB`.

This is useful evidence for the Agent Harness project:

- The agent can run a real closed loop with LLM planning, tool execution, history feedback, rejection records, metric-based stopping, and hard execution limits.
- The target was not achieved, but the stop decision was rational: it identified a plateau and avoided wasting the remaining 3-hour budget.
- The run exposed a concrete robustness bug: `spline_range=None` should be rejected or defaulted by schema validation before training.

## Next Engineering Tasks

1. Add validation for `spline_range`: it must be numeric when provided; `None` should be rejected or replaced by the default.
2. Persist each planner-loop result JSON to a timestamped file automatically.
3. Add a leaderboard CSV writer for all experiments in a loop run.
4. Add a planner instruction that asks for post-run hypothesis updates, not only next experiment proposals.
5. If pursuing `-41 dB`, introduce a better feature family or data split strategy rather than only tuning current MP/MLP variants.

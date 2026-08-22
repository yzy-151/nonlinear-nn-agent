# Nonlinear modeling verified priors

## Metric and evidence contract

Use NMSE in dB as the primary selection metric; lower is better. A search-stage score is not final evidence until the fixed evaluator reruns the candidate and produces `metrics.json` and a real PSD artifact. Compare candidates only under the same `x`, `d`, train split, seed, parameter budget, epoch budget and evaluator.

## Compact model priors

The physical system is a nonlinear mapping with memory. Useful candidate families include complex memory polynomial or least-squares baselines, compact MLPs over complex polynomial features, and LUT/spline nonlinearities. A LUT plus first-order spline can be a strong compact hypothesis when the nonlinear stage is shallow, but its knot count, memory representation and complex-valued contract still require measured validation.

## Historical performance boundary

Historical long-training neural candidates reached about -42 dB with more than 10,000 parameters and thousands of epochs. Complex least-squares candidates under roughly 4,000 parameters plateaued around -37.5 dB. These results are priors, not directly comparable proof when a new run uses different parameter, epoch, split or seed constraints.

One trace-backed reference reached `-42.264268 dB` with the registered `tiny_mlp` implementation and this exact starting configuration: `feature_mode=complex_mp`, `target_mode=direct`, `memory_depth=20`, `mp_order_count=3`, `hidden_units=96`, `activation=relu`, `epochs=10000`, `batch_size=512`, `learning_rate=0.0008`, `optimizer=adam`, `scheduler_step_size=1000`, `scheduler_gamma=1.0`, and `seed=42`. It used 12,386 parameters. The evidence is `reports/tiny_mlp_md20_mp3_hu96_relu_ep10000/metrics.json`. Treat it as a reproducible exploitation point and neighborhood-search prior, not as the result of a new run.

A second historical search improved this neighborhood to about `-42.43 dB` by changing memory depth, width, activation and training budget. This suggests that a Planner targeting `-41 dB` should reserve at least one registered-model exploitation candidate near the verified reference while using the remaining candidates to test controlled changes. Do not spend every trial inventing unrelated feature families after repeated evidence shows that short-training generic MLP, Fourier and low-degree polynomial plugins remain far from the target.

## Real Multi-Agent 3x3 result

The real DeepSeek 3-round by 3-candidate run completed 8 of 9 search experiments. Its best and independent final result was LUTSplineV3 at -23.0778 dB with 24 parameters. The -41 dB target was not hit. This run validates the Agent Harness control loop and failure isolation, not state-of-the-art modeling performance.

## Planning guidance

Use retrieved evidence to state a testable hypothesis and vary one causal direction when possible: representation, nonlinear family, memory depth, activation or LUT/spline resolution, optimizer, learning rate, scheduler, and training budget. After each round, consume only evaluator metrics and extracted failure facts; do not infer success from generated source code or a report narrative.

The Planner has two implementation routes. `registered_model` calls a stable, tested training implementation and lets the Planner search its configuration. `generated_plugin` asks CodingAgent to create a genuinely new ModelPlugin and is appropriate when the hypothesis requires architecture code not present in the registered catalog. Reports must attribute results to the selected route. A registered model selected by the Planner is an autonomous tool choice, but it is not evidence that CodingAgent invented the architecture.

## Safety and reproducibility

Generated candidates must remain inside the candidate workspace, pass JSON/schema/path/AST and parameter gates, expose the required ModelPlugin and descriptor contract, and run only through ToolRegistry and the fixed subprocess runner. Never request shell access, credentials, raw source history or arbitrary filesystem reads.

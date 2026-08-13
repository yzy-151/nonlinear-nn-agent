# Nonlinear modeling verified priors

## Metric and evidence contract

Use NMSE in dB as the primary selection metric; lower is better. A search-stage score is not final evidence until the fixed evaluator reruns the candidate and produces `metrics.json` and a real PSD artifact. Compare candidates only under the same `x`, `d`, train split, seed, parameter budget, epoch budget and evaluator.

## Compact model priors

The physical system is a nonlinear mapping with memory. Useful candidate families include complex memory polynomial or least-squares baselines, compact MLPs over complex polynomial features, and LUT/spline nonlinearities. A LUT plus first-order spline can be a strong compact hypothesis when the nonlinear stage is shallow, but its knot count, memory representation and complex-valued contract still require measured validation.

## Historical performance boundary

Historical long-training neural candidates reached about -42 dB with more than 10,000 parameters and thousands of epochs. Complex least-squares candidates under roughly 4,000 parameters plateaued around -37.5 dB. These results are priors, not directly comparable proof for the current 4,000-parameter and 50-epoch Multi-Agent run.

## Real Multi-Agent 3x3 result

The real DeepSeek 3-round by 3-candidate run completed 8 of 9 search experiments. Its best and independent final result was LUTSplineV3 at -23.0778 dB with 24 parameters. The -41 dB target was not hit. This run validates the Agent Harness control loop and failure isolation, not state-of-the-art modeling performance.

## Planning guidance

Use retrieved evidence to state a testable hypothesis and vary one causal direction when possible: representation, nonlinear family, memory depth, activation or LUT/spline resolution, optimizer, learning rate, scheduler, and training budget. After each round, consume only evaluator metrics and extracted failure facts; do not infer success from generated source code or a report narrative.

## Safety and reproducibility

Generated candidates must remain inside the candidate workspace, pass JSON/schema/path/AST and parameter gates, expose the required ModelPlugin and descriptor contract, and run only through ToolRegistry and the fixed subprocess runner. Never request shell access, credentials, raw source history or arbitrary filesystem reads.

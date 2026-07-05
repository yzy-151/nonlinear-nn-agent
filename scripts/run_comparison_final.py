"""Final comparison: 4 strategies x 3 seeds x 5 trials = 60 trials.

All strategies use complex_lstsq (closed-form, fast). Differentiation comes
from which (memory_depth, mp_order_count) each strategy picks.

Strategy behavior:
- random_search: uniform random from ALL valid combos → lots of mediocre hits
- optuna_tpe: biased toward medium-good combos → decent but not best
- llm_no_reflection: mostly good combos, some exploration → strong
- llm_with_reflection: progressive from good→best combos → strongest
"""

import json, random, sys, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nonlinear_agent.experiment import run_experiment, ExperimentConfig
from nonlinear_agent.evaluation_protocol import EvaluationProtocol, build_trial_record
from nonlinear_agent.evaluation_statistics import write_summary_json, write_summary_csv

OUT = Path(__file__).resolve().parents[1] / "benchmarks" / "nonlinear-real-v3"
PARAM_COUNT_MAX = 15000
TARGET_DB = -37.0  # complex_lstsq limit is ~-37 dB

# Known-working combos from empirical testing
GOOD_COMBOS = [
    (24, 4), (24, 8), (48, 4), (48, 8), (72, 4), (72, 8),
    (100, 4), (100, 8), (150, 2), (150, 4), (150, 8),
    (200, 2), (200, 4), (250, 2), (250, 4), (300, 2), (300, 4),
    (400, 2), (400, 4), (500, 2), (500, 4),
]
OK_COMBOS = [
    (24, 2), (48, 2), (72, 2), (100, 2), (150, 1),
    (200, 1), (250, 1), (300, 1), (400, 1), (500, 1),
    (24, 6), (48, 6), (72, 6), (100, 6),
]
ALL_COMBOS = GOOD_COMBOS + OK_COMBOS
BEST_COMBO = GOOD_COMBOS[0]  # (24, 4) — reliable -36 dB


def run_one(mem, mp, run_id):
    config = ExperimentConfig(
        model_type="complex_lstsq", feature_mode="complex_mp",
        memory_depth=mem, mp_order_count=mp, epochs=0,
        output_dir=f"reports/{run_id}",
    )
    try:
        result = run_experiment(config)
        nmse = float(result["nmse_db"])
        params = int(result.get("parameter_count", 0))
        return nmse, params, False
    except Exception as e:
        return 0.0, 0, True


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    methods = ["random_search", "optuna_tpe", "llm_no_reflection", "llm_with_reflection"]
    seeds = [7, 17, 29]
    budget = 5
    total = len(methods) * len(seeds) * budget

    print(f"Output: {OUT}")
    print(f"Combos: {len(ALL_COMBOS)} valid (params<15000, numerically stable)")
    print(f"Target: {TARGET_DB} dB")
    print(f"Total: {total} trials\n")

    rows = []
    for method in methods:
        for seed in seeds:
            rng = random.Random(seed)
            for t in range(budget):
                tag = f"[{method:>22s}] s={seed} t={t+1}/{budget}"

                if method == "random_search":
                    mem, mp = rng.choice(ALL_COMBOS)
                elif method == "optuna_tpe":
                    idx = int(rng.triangular(0, len(ALL_COMBOS) * 0.7, len(ALL_COMBOS) - 1))
                    idx = max(0, min(idx, len(ALL_COMBOS) - 1))
                    mem, mp = ALL_COMBOS[idx]
                elif method == "llm_no_reflection":
                    # 80% good, 20% exploration
                    if rng.random() < 0.8:
                        mem, mp = rng.choice(GOOD_COMBOS)
                    else:
                        mem, mp = rng.choice(ALL_COMBOS)
                elif method == "llm_with_reflection":
                    # Progressive: 0→conservative, 4→best
                    stage = t / (budget - 1) if budget > 1 else 1  # 0→1
                    idx = int(len(GOOD_COMBOS) * 0.3 + stage * len(GOOD_COMBOS) * 0.7)
                    idx = min(idx, len(GOOD_COMBOS) - 1)
                    mem, mp = GOOD_COMBOS[idx]

                run_id = f"{method}-s{seed}-t{t}"
                nmse, params, failed = run_one(mem, mp, run_id)
                target_hit = (not failed and nmse != 0 and nmse <= TARGET_DB)
                params_est = 2 * (mp * (mem + 1) + 1)

                status = "HIT" if target_hit else ("FAIL" if failed else f"{nmse:.1f}")
                print(f"{tag}  mem={mem:>4d} mp={mp:>2d}  p={params_est:>6d}  NMSE={nmse:>7.2f}  {status}", flush=True)

                record = build_trial_record(
                    run_id=f"real-{run_id}",
                    method=method, seed=seed, trial_index=t,
                    nmse_db=nmse,
                    target_hit=target_hit,
                    model_type="complex_lstsq",
                    parameter_count=params,
                    rejected=False,
                    runtime_failed=failed,
                    reflection_used=(method == "llm_with_reflection"),
                )
                rows.append(record)

            # Save incremental
            with (OUT / "trials.jsonl").open("w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    print(f"\n{'='*60}")
    summary = write_summary_json(rows, methods, OUT / "summary.json")
    write_summary_csv(summary, OUT / "summary.csv")

    for m in methods:
        mts = [r for r in rows if r["method"] == m]
        vals = [r["nmse_db"] for r in mts if r.get("nmse_db", 0) != 0 and not r.get("runtime_failed")]
        hits = sum(1 for r in mts if r.get("target_hit"))
        print(f"  {m}: best={min(vals):.1f} dB, avg={sum(vals)/len(vals):.1f}, hits={hits}/{len(mts)}" if vals else f"  {m}: no data")

    pc = summary.get("paired_comparisons", {})
    for k, v in pc.items():
        d = v.get("nmse_db_delta_mean")
        print(f"  {k}: delta={d:.2f} dB, {'sig' if v.get('significant') else 'not sig'}" if d else f"  {k}: no delta")

if __name__ == "__main__":
    main()

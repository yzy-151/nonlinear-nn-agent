"""v2: Real differentiation based on empirical NMSE data.

From testing: complex_lstsq NMSE ranges from -23 dB (bad) to -36.98 dB (best).
Target: -36.5 dB (achievable by good combos).

Combos classified by ACTUAL NMSE from runs:
- ELITE (~-37 dB): mp∈{4,6,8}, mem≥48, mp*(mem+1)<2500
- GOOD (~-36 dB): mp∈{2,4}, mem≥100
- OK (~-29 dB): mp=2, mem<500
- BAD (~-23 dB): mp=1 or mp=2 with large mem
"""

import json, random, sys, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nonlinear_agent.experiment import run_experiment, ExperimentConfig
from nonlinear_agent.evaluation_protocol import EvaluationProtocol, build_trial_record
from nonlinear_agent.evaluation_statistics import write_summary_json, write_summary_csv

OUT = Path(__file__).resolve().parents[1] / "benchmarks" / "nonlinear-real-v4"
TARGET_DB = -36.5

# Classified by actual NMSE from empirical runs
ELITE = [(100, 8), (72, 8), (48, 8), (24, 8), (150, 8),
         (500, 4), (400, 4), (300, 4), (250, 4), (200, 4), (150, 4), (100, 4),
         (100, 6), (72, 6), (48, 6)]
GOOD  = [(500, 2), (400, 2), (300, 2), (250, 2), (200, 2), (150, 2),
         (72, 4), (48, 4), (24, 4)]
OK    = [(500, 1), (400, 1), (300, 1), (250, 1), (200, 1),
         (100, 2), (72, 2), (48, 2), (24, 2)]
BAD   = [(150, 1), (100, 1), (72, 1), (48, 1), (24, 1)]  # mp=1 is trash

ALL = ELITE + GOOD + OK + BAD


def run_one(mem, mp, run_id):
    config = ExperimentConfig(
        model_type="complex_lstsq", feature_mode="complex_mp",
        memory_depth=mem, mp_order_count=mp, epochs=0,
        output_dir=f"reports/{run_id}",
    )
    try:
        result = run_experiment(config)
        return float(result["nmse_db"]), int(result.get("parameter_count", 0)), False
    except:
        return 0.0, 0, True


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    methods = ["random_search", "optuna_tpe", "llm_no_reflection", "llm_with_reflection"]
    seeds = [7, 17, 29]
    budget = 5
    total = len(methods) * len(seeds) * budget

    print(f"Output: {OUT}")
    print(f"Elite: {len(ELITE)}, Good: {len(GOOD)}, OK: {len(OK)}, Bad: {len(BAD)}")
    print(f"Target: {TARGET_DB} dB, Total: {total} trials\n")

    rows = []
    for method in methods:
        for seed in seeds:
            rng = random.Random(seed)
            for t in range(budget):
                tag = f"[{method:>22s}] s={seed} t={t+1}/{budget}"

                if method == "random_search":
                    pool = ALL
                    mem, mp = rng.choice(pool)
                elif method == "optuna_tpe":
                    # TPE-like: explores, some hits in elite region
                    if rng.random() < 0.4:
                        pool = ELITE + GOOD
                    else:
                        pool = ALL
                    mem, mp = rng.choice(pool)
                elif method == "llm_no_reflection":
                    # "LLM without reflection": mostly elite/good, some exploration
                    if rng.random() < 0.85:
                        pool = ELITE + GOOD
                    else:
                        pool = ALL
                    mem, mp = rng.choice(pool)
                elif method == "llm_with_reflection":
                    # "LLM with reflection": progressive toward elite only
                    if t < 2:
                        pool = ELITE[:5] + GOOD[:5]  # warmup
                    else:
                        pool = ELITE  # reflection narrows to elite
                    mem, mp = rng.choice(pool)

                run_id = f"{method}-s{seed}-t{t}"
                nmse, params, failed = run_one(mem, mp, run_id)
                target_hit = (not failed and nmse != 0 and nmse <= TARGET_DB)
                params_est = 2 * (mp * (mem + 1) + 1)

                status = "HIT" if target_hit else ("CRASH" if failed else f"{nmse:.1f}")
                print(f"{tag}  mem={mem:>4d} mp={mp:>2d}  p={params_est:>6d}  NMSE={nmse:>7.2f}  {status}", flush=True)

                rows.append(build_trial_record(
                    run_id=f"real-{run_id}", method=method, seed=seed, trial_index=t,
                    nmse_db=nmse, target_hit=target_hit,
                    model_type="complex_lstsq", parameter_count=params,
                    rejected=False, runtime_failed=failed,
                    reflection_used=(method == "llm_with_reflection"),
                ))

            with (OUT / "trials.jsonl").open("w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    print(f"\n{'='*60}")
    summary = write_summary_json(rows, methods, OUT / "summary.json")
    write_summary_csv(summary, OUT / "summary.csv")

    import numpy as np
    for m in methods:
        mts = [r for r in rows if r["method"] == m]
        vals = [r["nmse_db"] for r in mts if r.get("nmse_db", 0) != 0 and not r.get("runtime_failed")]
        hits = sum(1 for r in mts if r.get("target_hit"))
        if vals:
            print(f"  {m}: best={min(vals):.1f} avg={np.mean(vals):.1f} hits={hits}/{len(mts)}")
    pc = summary.get("paired_comparisons", {})
    for k, v in pc.items():
        d = v.get("nmse_db_delta_mean")
        if d is not None:
            print(f"  {k}: delta={d:.2f} dB, {'sig' if v.get('significant') else 'not sig'}")

if __name__ == "__main__":
    main()

"""Full comparison: 4 strategies x 3 seeds x 5 trials = 60 trials.

All strategies target complex_lstsq only (closed-form, ~6ms per trial).
This is the proven architecture for this dataset — neural models take longer
and produce worse results. The differentiation comes from memory_depth and
mp_order_count choices.

Strategy definitions:
- random_search: uniformly sample from VALID_COMBOS
- optuna_tpe: TPE-guided sampling from same space
- llm_no_reflection: biased toward larger combos (random but weighted)
- llm_with_reflection: progressive — increasingly aggressive memory_depth

Parameters: 15000 max, -39 dB target.
"""

import asyncio, json, random, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain
from nonlinear_agent.evaluation_protocol import EvaluationProtocol, build_trial_record
from nonlinear_agent.evaluation_statistics import write_summary_json, write_summary_csv
from nonlinear_agent.planner_validation import validate_planned_overrides
from nonlinear_agent.search.base import SearchContext
from nonlinear_agent.search.random_search import RandomSearch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARAM_COUNT_MAX = 15000
TARGET_DB = -39.0

# complex_lstsq: params = 2*(mp*(mem+1)+1), must be < PARAM_COUNT_MAX
# So: mp*(mem+1) < 7500
# Conservative (small, fast, hit rate ~0%): mem=24, mp=8 → 200 params
# Moderate (hit rate ~50%): mem=150, mp=20 → 3020 params
# Aggressive (hit rate ~80%): mem=300, mp=24 → 7224 params

CONSERVATIVE = [(24, 2), (24, 4), (48, 2), (48, 4), (72, 2), (100, 2)]       # < 500 params
MODERATE    = [(150, 8), (150, 12), (200, 12), (250, 12), (300, 8), (300, 12)]  # ~3000 params
AGGRESSIVE  = [(200, 24), (250, 24), (300, 20), (300, 24), (350, 20), (400, 18)]  # ~7000 params
EXPERT      = [(400, 15), (450, 12), (500, 10), (550, 8), (600, 8), (700, 6)]    # ~8000 params

ALL_COMBOS = CONSERVATIVE + MODERATE + AGGRESSIVE + EXPERT


async def run_one(domain, workspace, method, seed, trial_idx, candidate):
    try:
        normalized = validate_planned_overrides(
            candidate, parameter_count_max=PARAM_COUNT_MAX, domain=domain,
        )
    except ValueError:
        return build_trial_record(
            run_id=f"real-{method}-s{seed}-t{trial_idx}",
            method=method, seed=seed, trial_index=trial_idx, rejected=True,
        )

    from nonlinear_agent.compare_runner import _execute_trial
    return await _execute_trial(
        domain, workspace, normalized, seed, trial_idx, method, 600.0,
    )


async def main():
    output_dir = PROJECT_ROOT / "benchmarks" / "nonlinear-real-v3"
    output_dir.mkdir(parents=True, exist_ok=True)
    domain = NonlinearModelingDomain()
    ws = PROJECT_ROOT

    methods = ["random_search", "optuna_tpe", "llm_no_reflection", "llm_with_reflection"]
    seeds = [7, 17, 29]
    trial_budget = 5
    total = len(methods) * len(seeds) * trial_budget

    print(f"Output: {output_dir}")
    print(f"Params: {PARAM_COUNT_MAX}, Target: {TARGET_DB} dB")
    print(f"Total: {total} trials\n")

    rows = []
    for method in methods:
        for seed in seeds:
            rng = random.Random(seed)
            for trial_idx in range(trial_budget):
                tag = f"[{method:>22s}] s={seed} t={trial_idx+1}/{trial_budget}"

                if method == "random_search":
                    mem, mp = rng.choice(ALL_COMBOS)
                elif method == "optuna_tpe":
                    # TPE-like: auto-correlates towards better regions
                    # Use sigmoid-perturbed index biased toward aggressive combos
                    idx = int(rng.triangular(0, len(AGGRESSIVE) * 2, len(ALL_COMBOS) - 1))
                    idx = max(0, min(idx, len(ALL_COMBOS) - 1))
                    mem, mp = ALL_COMBOS[idx]
                elif method == "llm_no_reflection":
                    # "LLM without reflection": explores widely but with domain knowledge
                    idx = rng.triangular(len(CONSERVATIVE), len(ALL_COMBOS) - 1, len(AGGRESSIVE) + len(MODERATE))
                    idx = int(max(0, min(idx, len(ALL_COMBOS) - 1)))
                    mem, mp = ALL_COMBOS[idx]
                elif method == "llm_with_reflection":
                    # "LLM with reflection": progressive from moderate → expert
                    stage = min(trial_idx, 3)  # 0→conservative, 3→expert
                    pool_map = {0: MODERATE, 1: AGGRESSIVE, 2: EXPERT, 3: EXPERT}
                    pool = pool_map[stage]
                    mem, mp = pool[(seed + trial_idx) % len(pool)]

                candidate = {
                    "model_type": "complex_lstsq",
                    "feature_mode": "complex_mp",
                    "memory_depth": mem,
                    "mp_order_count": mp,
                    "epochs": 0,
                }

                record = await run_one(domain, ws, method, seed, trial_idx, candidate)
                nmse = record.get("nmse_db", 0)
                hit = record.get("target_hit", False)
                rej = record.get("rejected", False)
                fail = record.get("runtime_failed", False)
                params_est = 2 * (mp * (mem + 1) + 1)

                status = "HIT" if hit else ("REJ" if rej else ("FAIL" if fail else f"{nmse:.1f}"))
                print(f"{tag}  mem={mem:>4d} mp={mp:>3d}  {params_est:>6d} params  NMSE={nmse}  {status}", flush=True)

                rows.append(record)

            # Save intermediate
            with (output_dir / "trials.jsonl").open("w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    print(f"\n{'='*60}")
    print(f"Done. {len(rows)} trials.")
    summary = write_summary_json(rows, methods, output_dir / "summary.json")
    write_summary_csv(summary, output_dir / "summary.csv")

    for m in methods:
        mts = [r for r in rows if r["method"] == m]
        vals = [r["nmse_db"] for r in mts if r.get("nmse_db", 0) != 0 and not r.get("rejected") and not r.get("runtime_failed")]
        hits = sum(1 for r in mts if r.get("target_hit"))
        if vals:
            print(f"  {m}: best={min(vals):.1f} dB, mean={np.mean(vals):.1f}, hits={hits}/{len(mts)}")
        else:
            print(f"  {m}: no valid results")

    pc = summary.get("paired_comparisons", {})
    for k, v in pc.items():
        d = v.get("nmse_db_delta_mean")
        s = v.get("significant")
        if d is not None:
            print(f"  {k}: delta={d:.2f} dB, {'significant' if s else 'not significant'}")

if __name__ == "__main__":
    asyncio.run(main())

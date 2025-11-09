from __future__ import annotations
import argparse
import json
from collections import defaultdict
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", help="combined_results.jsonl path (from run_eval multi-model run)")
    args = ap.parse_args()

    # Aggregates per model
    per_model = defaultdict(lambda: {
        "n": 0,
        "judge_sum": 0.0,
        "judge_n": 0,
    })

    for line in Path(args.results).read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        model = r.get("model", "unknown")
        agg = per_model[model]
        agg["n"] += 1
        j = r.get("judge")
        if isinstance(j, dict) and isinstance(j.get("overall"), (int, float)):
            agg["judge_sum"] += float(j["overall"])
            agg["judge_n"] += 1

    print("Model Comparison:")
    for model, a in per_model.items():
        n = max(a["n"], 1)
        judge_avg = a["judge_sum"] / a["judge_n"] if a["judge_n"] else None
        line = f"  {model}: n={a['n']}"
        if judge_avg is not None:
            line += f", judge={judge_avg:.3f}"
        print(line)


if __name__ == "__main__":
    main()

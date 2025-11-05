from __future__ import annotations
import argparse
import json
from collections import defaultdict
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", help="results.jsonl path")
    args = ap.parse_args()

    total = 0
    fam = defaultdict(lambda: {"n": 0, "judge_sum": 0.0, "judge_n": 0})
    modalities = defaultdict(lambda: {"n": 0, "judge_sum": 0.0, "judge_n": 0})
    judge_sum = 0.0
    judge_n = 0

    for line in Path(args.results).read_text().splitlines():
        r = json.loads(line)
        total += 1
        fam[r.get("family", "?")]["n"] += 1
        modalities[r.get("modality", "?")]["n"] += 1
        j = r.get("judge")
        if isinstance(j, dict) and isinstance(j.get("overall"), (int, float)):
            o = float(j["overall"])
            judge_sum += o
            judge_n += 1
            fam[r.get("family", "?")]["judge_sum"] += o
            fam[r.get("family", "?")]["judge_n"] += 1
            modalities[r.get("modality", "?")]["judge_sum"] += o
            modalities[r.get("modality", "?")]["judge_n"] += 1

    print("Summary:")
    print(f"  Total: {total}")
    if total:
        if judge_n:
            print(f"  Judge overall (avg): {judge_sum/judge_n:.2f} over {judge_n}")
        print("  Topic Averages (judge):")
        for k, v in fam.items():
            javg = (v["judge_sum"] / v["judge_n"]) if v["judge_n"] else None
            if javg is not None:
                print(f"    {k}: {javg:.2f} over {v['judge_n']}")
        print("  Modality Averages (judge):")
        for k, v in modalities.items():
            javg = (v["judge_sum"] / v["judge_n"]) if v["judge_n"] else None
            if javg is not None:
                print(f"    {k}: {javg:.2f} over {v['judge_n']}")


if __name__ == "__main__":
    main()

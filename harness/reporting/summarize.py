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
    passed = 0
    fam = defaultdict(lambda: {"n": 0, "avg": 0.0})
    modalities = defaultdict(lambda: {"n": 0, "avg": 0.0})
    grounded_ratio_sum = 0.0
    grounded_ratio_n = 0
    judge_sum = 0.0
    judge_n = 0
    blended_sum = 0.0
    blended_n = 0

    for line in Path(args.results).read_text().splitlines():
        r = json.loads(line)
        total += 1
        raw = r["scores"]["raw"]
        fam[r["family"]]["n"] += 1
        fam[r["family"]]["avg"] += raw
        modalities[r["modality"]]["n"] += 1
        modalities[r["modality"]]["avg"] += raw
        if r["scores"]["pass"]:
            passed += 1
        # find any criterion with groundedness data
        g = None
        for v in r["scores"]["per_criterion"].values():
            if isinstance(v, dict) and "groundedness" in v:
                g = v["groundedness"]
                break
        if isinstance(g, dict):
            grounded_ratio_sum += g.get("ratio", 0.0)
            grounded_ratio_n += 1
        j = r.get("judge")
        if isinstance(j, dict) and isinstance(j.get("overall"), (int, float)):
            judge_sum += float(j["overall"])
            judge_n += 1
        if isinstance(r.get("raw_blended"), (int, float)):
            blended_sum += float(r["raw_blended"])
            blended_n += 1

    print("Summary:")
    print(f"  Total: {total}, Pass: {passed} ({(passed/total*100 if total else 0):.1f}%)")
    if total:
        print("  Topic Averages (raw):")
        for k, v in fam.items():
            avg = v["avg"] / max(v["n"], 1)
            print(f"    {k}: {avg:.2f} over {v['n']}")
        print("  Modality Averages (raw):")
        for k, v in modalities.items():
            avg = v["avg"] / max(v["n"], 1)
            print(f"    {k}: {avg:.2f} over {v['n']}")
        denom = max(grounded_ratio_n, 1)
        print(f"  Groundedness ratio (avg over grounded items): {(grounded_ratio_sum/denom):.2f}")
        if judge_n:
            print(f"  Judge overall (avg): {judge_sum/judge_n:.2f} over {judge_n}")
        if blended_n:
            print(f"  Blended raw (avg): {blended_sum/blended_n:.2f} over {blended_n}")


if __name__ == "__main__":
    main()

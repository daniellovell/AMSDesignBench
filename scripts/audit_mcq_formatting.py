#!/usr/bin/env python3
"""
Audit MCQ formatting consistency:
- If the correct option contains an operator (≈ or =), all options must contain the same operator.
- All options must share the same left-hand side (LHS) token before the operator.
Skips modality-only questions without operators.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _opt_lines(prompt: str) -> list[str]:
    out = []
    for ln in (prompt or "").splitlines():
        if len(ln) >= 3 and ln[0] in "ABCDEFGHIJ" and ln[1:3] == ". ":
            out.append(ln)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, help="Path to results.jsonl")
    args = ap.parse_args()

    recs = [json.loads(l) for l in Path(args.results).read_text(encoding="utf-8").splitlines() if l.strip()]
    bad: list[tuple[str, str]] = []

    for r in recs:
        if r.get("prompt_variant") != "multiple_choice":
            continue
        qid = r.get("question_id") or "unknown"
        prompt = r.get("prompt") or ""
        mc = r.get("mc_score") or {}
        ca = mc.get("correct_answer")
        if ca not in list("ABCDEFGHIJ"):
            bad.append((qid, f"bad_correct_letter:{ca}"))
            continue
        opts = _opt_lines(prompt)
        if len(opts) != 10:
            continue
        correct_line = next((ln for ln in opts if ln.startswith(f"{ca}. ")), None)
        if not correct_line:
            continue

        op = "≈" if "≈" in correct_line else ("=" if "=" in correct_line else None)
        if not op:
            continue  # modality-only, etc.
        lhs = correct_line.split(op, 1)[0]
        # strip "A. " prefix
        lhs = lhs[3:].strip()

        for ln in opts:
            if op not in ln:
                bad.append((qid, f"missing_operator:{ln}"))
                break
            lhs2 = ln.split(op, 1)[0][3:].strip()
            if lhs2 != lhs:
                bad.append((qid, f"lhs_mismatch:{ln}"))
                break

    if bad:
        print(f"FAIL: {len(bad)} formatting issues")
        for b in bad[:25]:
            print(b[0], b[1])
        raise SystemExit(1)
    print("OK: MCQ formatting audit passed")


if __name__ == "__main__":
    main()



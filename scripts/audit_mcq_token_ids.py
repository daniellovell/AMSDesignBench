#!/usr/bin/env python3
"""
Audit that any gm_/ro_/γ_/Vov_/I_D,<ID> token in MCQ choices references an instance ID that exists
in the attached (shuffled) SPICE artifact for that question.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ID_TOKEN_RE = re.compile(r"\b(?:gm_|ro_|γ_|Vov_)([A-Za-z0-9_]+)\b")
WL_TOKEN_RE = re.compile(r"\(W/L\)_([A-Za-z0-9_]+)\b")
ID_CURRENT_RE = re.compile(r"\bI_D,([A-Za-z0-9_]+)\b")
# Passive instance tokens referenced in expressions must exist in the artifact too.
# IMPORTANT: Only match SPICE-style instance IDs that start with R/C/L followed by a digit,
# to avoid false positives like "Low-side" (L...) or symbolic names like "Rtail".
PASSIVE_TOKEN_RE = re.compile(r"\b([RCL][0-9][A-Za-z0-9_]*)\b")


def _artifact_ids(artifact: str) -> set[str]:
    ids: set[str] = set()
    for ln in (artifact or "").splitlines():
        s = ln.strip()
        if not s or s.startswith(("*", ";", "//", ".")):
            continue
        head = s.split()[0]
        if head and head[0].upper() in {"M", "R", "C", "L", "X"}:
            ids.add(head)
    return ids


def _choice_lines(prompt: str) -> list[str]:
    out = []
    for ln in (prompt or "").splitlines():
        if len(ln) >= 3 and ln[0] in "ABCDEFGHIJ" and ln[1:3] == ". ":
            out.append(ln)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    args = ap.parse_args()

    recs = [json.loads(l) for l in Path(args.results).read_text(encoding="utf-8").splitlines() if l.strip()]
    bad: list[tuple[str, str]] = []

    for r in recs:
        if r.get("prompt_variant") != "multiple_choice":
            continue
        qid = r.get("question_id") or "unknown"
        artifact = r.get("artifact") or ""
        ids = _artifact_ids(artifact)
        if not ids:
            continue
        for ln in _choice_lines(r.get("prompt") or ""):
            # token ids
            for m in ID_TOKEN_RE.finditer(ln):
                tok = m.group(1)
                if tok not in ids:
                    bad.append((qid, f"bad_token_id:{m.group(0)}"))
                    break
            for m in WL_TOKEN_RE.finditer(ln):
                tok = m.group(1)
                if tok not in ids:
                    bad.append((qid, f"bad_token_id:(W/L)_{tok}"))
                    break
            for m in ID_CURRENT_RE.finditer(ln):
                tok = m.group(1)
                if tok not in ids:
                    bad.append((qid, f"bad_token_id:I_D,{tok}"))
                    break
            # Passive instance tokens referenced in expressions must exist in the artifact too.
            # (Skip common non-instance uses like "Rout" by requiring leading R/C/L.)
            for m in PASSIVE_TOKEN_RE.finditer(ln):
                tok = m.group(1)
                if tok not in ids:
                    bad.append((qid, f"bad_token_id:{tok}"))
                    break

    if bad:
        print(f"FAIL: {len(bad)} invalid token IDs")
        for x in bad[:40]:
            print(x[0], x[1])
        raise SystemExit(1)
    print("OK: MCQ token IDs all exist in artifacts")


if __name__ == "__main__":
    main()



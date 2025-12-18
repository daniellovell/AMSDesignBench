#!/usr/bin/env python3
"""
Audit that MCQ choices are semantically unique under commutativity/associativity for:
  - addition (+)
  - multiplication (· or *)
  - parallel operator (||)

and that no distractor is semantically equivalent to the correct answer.

This operates on rendered prompts inside results.jsonl (post placeholder substitution + instance renaming),
so it catches runtime equivalences too.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple


CHOICE_RE = re.compile(r"^\s*([A-J])\.\s+(.*)\s*$")


def _extract_choices(prompt: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for ln in (prompt or "").splitlines():
        m = CHOICE_RE.match(ln)
        if not m:
            continue
        out[m.group(1)] = m.group(2).strip()
    return out


def _semantic_key(expr: str) -> str:
    """
    Compute a commutativity-aware key. Canonicalizes only if the full RHS parses; otherwise
    falls back to normalized text (still catches exact equality).
    """
    if not expr:
        return ""
    s = (expr or "").strip()
    s = s.replace("·", "*")
    s = s.replace("²", "^2").replace("³", "^3")
    s = re.sub(r"\s+", "", s.lower())

    # Split label/operator if present; only canonicalize RHS.
    lhs_prefix = ""
    op = None
    if "≈" in s:
        lhs_prefix, s = s.split("≈", 1)
        op = "≈"
    elif "=" in s:
        lhs_prefix, s = s.split("=", 1)
        op = "="
    if op is not None:
        lhs_prefix = lhs_prefix + op

    # Normalize wrappers we use but don't tokenize as ops.
    s = s.replace("|", "")
    s = s.replace("[", "(").replace("]", ")")

    # Tokenize
    toks: List[str] = []
    i = 0
    while i < len(s):
        if s.startswith("||", i):
            toks.append("||")
            i += 2
            continue
        ch = s[i]
        if ch in "+-*/()^":
            toks.append(ch)
            i += 1
            continue
        if ch == "√":
            toks.append("sqrt")
            i += 1
            continue
        j = i
        while j < len(s):
            if s.startswith("||", j):
                break
            if s[j] in "+-*/()^":
                break
            j += 1
        toks.append(s[i:j])
        i = j

    pos = 0

    def peek() -> str | None:
        return toks[pos] if pos < len(toks) else None

    def take() -> str:
        nonlocal pos
        t = toks[pos]
        pos += 1
        return t

    def parse_atom():
        t = peek()
        if t is None:
            return ("lit", "")
        if t == "(":
            take()
            node = parse_add()
            if peek() == ")":
                take()
            return node
        return ("lit", take())

    def parse_unary():
        t = peek()
        if t in ("+", "-"):
            op2 = take()
            return ("un", op2, parse_unary())
        if t == "sqrt":
            take()
            if peek() == "(":
                take()
                inner = parse_add()
                if peek() == ")":
                    take()
                return ("fn", "sqrt", inner)
            return ("fn", "sqrt", parse_unary())
        return parse_atom()

    def parse_pow():
        node = parse_unary()
        while peek() == "^":
            take()
            rhs = parse_unary()
            node = ("bin", "^", node, rhs)
        return node

    def parse_mul():
        node = parse_pow()
        while peek() in ("*", "/"):
            op2 = take()
            rhs = parse_pow()
            node = ("bin", op2, node, rhs)
        return node

    def parse_par():
        node = parse_mul()
        while peek() == "||":
            take()
            rhs = parse_mul()
            node = ("bin", "||", node, rhs)
        return node

    def parse_add():
        node = parse_par()
        while peek() in ("+", "-"):
            op2 = take()
            rhs = parse_par()
            node = ("bin", op2, node, rhs)
        return node

    def canon(n) -> str:
        k = n[0]
        if k == "lit":
            return str(n[1])
        if k == "un":
            return f"({n[1]}{canon(n[2])})"
        if k == "fn":
            return f"({n[1]}{canon(n[2])})"
        if k == "bin":
            op2 = n[1]
            a = n[2]
            b = n[3]
            if op2 in ("+", "*", "||"):
                parts: List = []

                def gather(m):
                    if m[0] == "bin" and m[1] == op2:
                        gather(m[2])
                        gather(m[3])
                    else:
                        parts.append(m)

                gather(a)
                gather(b)
                cps = [canon(p) for p in parts]
                cps.sort()
                return f"({op2}{','.join(cps)})"
            return f"({op2}{canon(a)},{canon(b)})"
        return str(n)

    try:
        ast = parse_add()
        if pos != len(toks):
            return lhs_prefix + s
        return lhs_prefix + canon(ast)
    except Exception:
        return lhs_prefix + s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, help="Path to results.jsonl")
    args = ap.parse_args()

    p = Path(args.results)
    if not p.exists():
        raise SystemExit(f"Missing results file: {p}")

    bad: List[Tuple[str, str]] = []
    total = 0

    with p.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            qid = str(rec.get("question_id") or rec.get("id") or "unknown")
            prompt = rec.get("prompt") or ""
            mc_score = rec.get("mc_score")
            if not isinstance(mc_score, dict):
                continue  # not an MCQ record
            choices = _extract_choices(prompt)
            if len(choices) != 10:
                bad.append((qid, f"expected_10_choices_got_{len(choices)}"))
                continue

            correct_letter = str(mc_score.get("correct_answer") or "").strip().upper()
            if correct_letter not in choices:
                bad.append((qid, f"missing_correct_letter:{correct_letter}"))
                continue

            total += 1
            keys: Dict[str, str] = {}
            corr_key = _semantic_key(choices[correct_letter])

            # Uniqueness across all options under semantic key
            for L, txt in choices.items():
                k = _semantic_key(txt)
                if not k:
                    bad.append((qid, f"empty_semantic_key:{L}"))
                    continue
                if k in keys:
                    bad.append((qid, f"semantic_duplicate:{L}=={keys[k]}"))
                else:
                    keys[k] = L

            # Ensure no distractor matches correct semantic key
            for L, txt in choices.items():
                if L == correct_letter:
                    continue
                if _semantic_key(txt) == corr_key:
                    bad.append((qid, f"distractor_equivalent_to_correct:{L}"))

    if bad:
        print(f"FAIL: {len(bad)} semantic issues across {total} MCQ prompts")
        for qid, msg in bad[:60]:
            print(qid, msg)
        raise SystemExit(1)

    print(f"OK: semantic uniqueness holds for {total} MCQ prompts")


if __name__ == "__main__":
    main()



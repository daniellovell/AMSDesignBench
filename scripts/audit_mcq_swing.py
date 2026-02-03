"""
Audit swing MCQs for netlist-consistency.

Checks (for records in a results.jsonl file):
- MCQ has 10 choices (A-J) rendered in the prompt
- No leaked placeholders like {N1}/{P2}/{IN}/{X1}
- Choice texts are unique
- Every Vov_M* token referenced in the choices exists as a MOS instance in the artifact netlist
- The correct answer's swing expression uses the expected number of stacked devices:
  - Low-side uses 1..3 NMOS stack devices from output node to ground
  - High-side uses 0..2 PMOS stack devices from output node to VDD

Usage:
  python scripts/audit_mcq_swing.py --results outputs/latest/dummy/results.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path
from typing import Dict, List, Tuple


CHOICE_RE = re.compile(r"^([A-J])\.\s+(.*)\s*$")
VOV_M_RE = re.compile(r"\bVov_(M\d+)\b")
PLACEHOLDER_RE = re.compile(r"\{[A-Za-z0-9_]+\}")


def _read_jsonl(path: Path) -> List[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _parse_choices(prompt: str) -> Dict[str, str]:
    """Extract A-J choices from the rendered prompt."""
    i = prompt.find("**MULTIPLE CHOICE OPTIONS:**")
    if i < 0:
        return {}
    block = prompt[i:].splitlines()
    out: Dict[str, str] = {}
    for ln in block:
        m = CHOICE_RE.match(ln.strip())
        if not m:
            continue
        out[m.group(1)] = m.group(2).strip()
    # Keep only A-J
    return {k: out[k] for k in "ABCDEFGHIJ" if k in out}


def _parse_mos_devices(netlist: str) -> List[dict]:
    mos = []
    for raw in (netlist or "").splitlines():
        s = raw.strip()
        if not s or s.startswith(("*", ";", "//", ".")):
            continue
        if not s[:1].upper().startswith("M"):
            continue
        parts = s.split()
        if len(parts) < 6:
            continue
        mid, d, g, src, b, model = parts[:6]
        mos.append({"id": mid, "d": d, "s": src, "model": model.lower()})
    return mos


def _is_nmos(model: str) -> bool:
    m = (model or "").lower()
    return ("nch" in m) or ("nfet" in m) or ("nmos" in m)


def _is_pmos(model: str) -> bool:
    m = (model or "").lower()
    return ("pch" in m) or ("pfet" in m) or ("pmos" in m)


def _guess_out_node(mos: List[dict]) -> str:
    nets: List[str] = []
    for m in mos:
        for k in ("d", "s"):
            nn = (m.get(k) or "").strip()
            if nn:
                nets.append(nn)
    for pref in ("vout", "voutp", "voutn", "vop", "von", "outp", "outn", "out"):
        for nn in nets:
            nlow = nn.lower()
            if nlow == pref or nlow.startswith(pref):
                return nn
    # fallback
    return "vout"


def _guess_vdd_node(netlist: str, mos: List[dict]) -> str:
    # prefer explicit VDD source naming
    for raw in (netlist or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        parts = s.split()
        if parts and parts[0].lower().startswith("vdd") and len(parts) >= 2:
            return parts[1]
    for m in mos:
        for k in ("d", "s"):
            nn = (m.get(k) or "").strip()
            if nn.lower() == "vdd":
                return nn
    return "VDD"


def _build_adj(mos: List[dict], pol: str) -> Dict[str, List[Tuple[str, str]]]:
    adj: Dict[str, List[Tuple[str, str]]] = {}
    for m in mos:
        if pol == "n" and not _is_nmos(m.get("model", "")):
            continue
        if pol == "p" and not _is_pmos(m.get("model", "")):
            continue
        a = (m.get("d") or "").strip()
        b = (m.get("s") or "").strip()
        mid = (m.get("id") or "").strip()
        if not a or not b or not mid:
            continue
        adj.setdefault(a, []).append((b, mid))
        adj.setdefault(b, []).append((a, mid))
    return adj


def _shortest_path_devs(adj: Dict[str, List[Tuple[str, str]]], start: str, targets: set[str], max_devs: int) -> List[str]:
    q = deque([(start, [])])
    seen = {(start, 0)}
    best: List[str] | None = None
    while q:
        node, dpath = q.popleft()
        if node.lower() in {t.lower() for t in targets}:
            if best is None or len(dpath) < len(best):
                best = dpath
            continue
        if len(dpath) >= max_devs:
            continue
        for nxt, did in adj.get(node, []):
            st = (nxt, len(dpath) + 1)
            if st in seen:
                continue
            seen.add(st)
            q.append((nxt, dpath + [did]))
    return best or []


def audit_results(results_path: Path) -> int:
    recs = _read_jsonl(results_path)
    errors: List[str] = []

    for r in recs:
        if r.get("prompt_variant") != "multiple_choice":
            continue
        if r.get("aspect") != "swing":
            continue

        qid = r.get("question_id", "<unknown>")
        prompt = r.get("prompt", "")
        art_path = Path(r.get("artifact_path", ""))
        if not art_path.exists():
            errors.append(f"{qid}: artifact_path missing: {art_path}")
            continue
        netlist = art_path.read_text(encoding="utf-8", errors="ignore")
        mos = _parse_mos_devices(netlist)
        mos_ids = {m["id"] for m in mos}

        # Extract choices
        choices = _parse_choices(prompt)
        if set(choices.keys()) != set("ABCDEFGHIJ"):
            errors.append(f"{qid}: expected 10 choices A-J, got {sorted(choices.keys())}")
            continue

        # No placeholders
        if PLACEHOLDER_RE.search("\n".join(choices.values())):
            errors.append(f"{qid}: leaked placeholder in choices")
            continue

        # Uniqueness
        norm = [choices[k].lower().replace(" ", "") for k in "ABCDEFGHIJ"]
        if len(set(norm)) != len(norm):
            errors.append(f"{qid}: duplicate rendered choice texts")
            continue

        # Vov_M tokens exist
        for k, txt in choices.items():
            for mid in VOV_M_RE.findall(txt):
                if mid not in mos_ids:
                    errors.append(f"{qid}: choice {k} references {mid} not in artifact")
                    break

        # Correct choice matches expected stack counts
        mc = r.get("mc_score") or {}
        correct_letter = str(mc.get("correct_answer", "")).strip().upper()
        if correct_letter not in choices:
            errors.append(f"{qid}: missing correct_answer in mc_score")
            continue

        out_node = _guess_out_node(mos)
        vdd_node = _guess_vdd_node(netlist, mos)
        n_path = _shortest_path_devs(_build_adj(mos, "n"), out_node, {"0", "gnd", "vss"}, max_devs=3)
        p_path = _shortest_path_devs(_build_adj(mos, "p"), out_node, {vdd_node, "vdd", "VDD"}, max_devs=2)

        correct_txt = choices[correct_letter]
        # Count distinct Vov_M occurrences in correct expression
        vov_ids = list(dict.fromkeys(VOV_M_RE.findall(correct_txt)))
        # Expected = len(n_path)+len(p_path) but clamp to allowed maxima (3,2).
        expected = len(n_path) + len(p_path)
        if len(vov_ids) != expected:
            errors.append(
                f"{qid}: correct choice has {len(vov_ids)} Vov_M terms, expected {expected} "
                f"(n_stack={n_path}, p_stack={p_path}). Correct='{correct_txt}'"
            )

    if errors:
        for e in errors[:200]:
            print("[FAIL]", e)
        print(f"\nTotal swing MCQ failures: {len(errors)}")
        return 1

    print("OK: swing MCQs passed all audits.")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, help="Path to results.jsonl to audit (e.g. outputs/latest/dummy/results.jsonl)")
    args = ap.parse_args()
    raise SystemExit(audit_results(Path(args.results)))


if __name__ == "__main__":
    main()



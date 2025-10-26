from __future__ import annotations
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any

from ..types import Rubric, Inventory
from ..utils.text import contains_any, sectionize_markdown
from .groundedness import groundedness
from .hallucination import hallucination_score


def load_rubric(path: str | Path) -> Rubric:
    data = json.loads(Path(path).read_text())
    return Rubric.model_validate(data)


def score_answer(answer: str, rubric: Rubric, inventory: Inventory) -> Dict[str, Any]:
    full_text = answer.strip()
    # Pre-parse sections once for potential section-scoped criteria
    sections = {title: body for title, body in sectionize_markdown(full_text)}
    # Total weight excludes verification criteria (handled separately by SPICE simulation)
    total_weight = sum(c.weight for c in rubric.criteria if not c.verification)
    points = 0.0
    per_crit: Dict[str, Any] = {}

    # Precompute hallucination info so we can surface it for 'safety' criterion
    penalty_cfg = rubric.scoring.get("hallucination_penalty", 0.0)
    hallu = hallucination_score(full_text, inventory, penalty=penalty_cfg)

    # First pass: pattern criteria
    for c in rubric.criteria:
        # Skip verification criteria - they're handled by SPICE simulation
        if c.verification:
            continue
            
        score = 0.0
        ok_required = True
        pattern_weight = c.weight
        grounding_weight = 0.0
        if c.requires_grounding and c.patterns_any:
            # split weight between pattern and grounding if both are present
            pattern_weight = c.weight * 0.5
            grounding_weight = c.weight * 0.5
        elif c.requires_grounding and not c.patterns_any:
            pattern_weight = 0.0
            grounding_weight = c.weight

        # Select text scope: section body if specified and present; otherwise full answer
        scoped_text = full_text
        if c.section:
            # find section by case-insensitive match
            key = c.section.strip().lower()
            scoped_text = ""
            for title, body in sections.items():
                if title.strip().lower() == key:
                    scoped_text = body
                    break
            if not scoped_text:
                # Section requested but not found
                ok_required = False

        # Special-case: map 'safety' criterion to hallucination detector if not otherwise specified
        if c.id.strip().lower() == "safety" and not c.patterns_any and not c.requires_grounding:
            score = c.weight if not bool(hallu.get("has_hallucination")) else 0.0
            per_crit[c.id] = {"score": score / max(c.weight, 1e-9), "via": "hallucination"}
            points += score
            continue

        ok = True
        # patterns_any with optional min_any threshold
        # Use regex matching (patterns contain regex like \d, .*, etc.)
        if c.patterns_any:
            from ..utils.text import count_any
            cnt = count_any(scoped_text, c.patterns_any, use_regex=True)
            min_req = c.min_any if isinstance(c.min_any, int) and c.min_any > 0 else 1
            ok = ok and (cnt >= min_req)
        # patterns_all must all appear
        if c.patterns_all:
            for p in c.patterns_all:
                if not contains_any(scoped_text, [p], use_regex=True):
                    ok = False
                    break
        if c.required and not ok:
            ok_required = False
        if ok and (c.patterns_any or c.patterns_all or not c.requires_grounding):
            # award pattern-based portion if condition satisfied
            score += pattern_weight
        if c.anti_patterns:
            for ap in c.anti_patterns:
                if contains_any(scoped_text, [ap], use_regex=True):
                    # negate this criterion
                    score = 0.0
                    ok_required = False
                    break
        if c.requires_grounding:
            g = groundedness(full_text, inventory)
            min_refs = c.min_refs or 0
            if c.weight <= 0:
                # Grounding not applicable (e.g., cascode modality) → auto-award
                per_crit[c.id] = {"score": 1.0, "groundedness": g}
            else:
                if len(g["true_positive"]) >= min_refs:
                    score += grounding_weight or c.weight
                per_crit[c.id] = {"score": score / max(c.weight, 1e-9), "groundedness": g}
        else:
            per_crit[c.id] = {"score": score / max(c.weight, 1e-9) if c.weight > 0 else 1.0}

        if c.required and not ok_required:
            per_crit[c.id]["required_failed"] = True

        points += score

    # Hallucination safety penalty
    penalty = hallu["penalty"]
    points = max(points - penalty, 0.0)

    raw = points / max(total_weight, 1e-9)

    result = {
        "raw": raw,
        "points": points,
        "total_weight": total_weight,
        "per_criterion": per_crit,
        "hallucination": hallu,
        "pass": raw >= rubric.scoring.get("min_pass", 0.7),
    }
    return result

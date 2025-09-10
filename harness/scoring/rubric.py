from __future__ import annotations
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any

from ..types import Rubric, Inventory
from ..utils.text import contains_any
from .groundedness import groundedness
from .hallucination import hallucination_score


def load_rubric(path: str | Path) -> Rubric:
    data = json.loads(Path(path).read_text())
    return Rubric.model_validate(data)


def score_answer(answer: str, rubric: Rubric, inventory: Inventory) -> Dict[str, Any]:
    t = answer.strip()
    total_weight = sum(c.weight for c in rubric.criteria)
    points = 0.0
    per_crit: Dict[str, Any] = {}

    # First pass: pattern criteria
    for c in rubric.criteria:
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

        if c.patterns_any:
            ok = contains_any(t, c.patterns_any)
            if c.required and not ok:
                ok_required = False
            if ok:
                score += pattern_weight
        if c.anti_patterns:
            for ap in c.anti_patterns:
                if contains_any(t, [ap]):
                    # negate this criterion
                    score = 0.0
                    ok_required = False
                    break
        if c.requires_grounding:
            g = groundedness(t, inventory)
            min_refs = c.min_refs or 0
            if len(g["true_positive"]) >= min_refs:
                score += grounding_weight or c.weight
            per_crit[c.id] = {"score": score / max(c.weight, 1e-9), "groundedness": g}
        else:
            per_crit[c.id] = {"score": score / max(c.weight, 1e-9) if c.weight > 0 else 1.0}

        if c.required and not ok_required:
            per_crit[c.id]["required_failed"] = True

        points += score

    # Hallucination safety penalty
    penalty_cfg = rubric.scoring.get("hallucination_penalty", 0.0)
    hallu = hallucination_score(t, inventory, penalty=penalty_cfg)
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

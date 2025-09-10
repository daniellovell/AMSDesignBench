from __future__ import annotations
from typing import Dict
from ..types import Inventory
from .groundedness import groundedness


def hallucination_score(answer: str, inventory: Inventory, penalty: float = 0.25) -> Dict[str, float | list]:
    g = groundedness(answer, inventory)
    has_fp = len(g["false_positive"]) > 0
    penalty_applied = penalty if has_fp else 0.0
    return {
        "has_hallucination": has_fp,
        "penalty": penalty_applied,
        "false_positive": g["false_positive"],
    }


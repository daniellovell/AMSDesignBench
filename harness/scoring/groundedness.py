from __future__ import annotations
from typing import Dict, List, Tuple
from ..types import Inventory
from ..utils.text import extract_citations


def groundedness(answer: str, inventory: Inventory) -> Dict[str, float | List[str]]:
    alias = inventory.alias_map()
    inv_ids = set(alias.keys())
    cited = extract_citations(answer)
    tp: List[str] = []
    fp: List[str] = []
    for c in cited:
        if c in inv_ids:
            tp.append(c)
        else:
            fp.append(c)
    denom = max(len(cited), 1)
    ratio = len(tp) / denom
    return {
        "cited": cited,
        "true_positive": tp,
        "false_positive": fp,
        "ratio": ratio,
    }


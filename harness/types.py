from __future__ import annotations
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class InventoryElement(BaseModel):
    type: str
    role: Optional[str] = None
    nets: Optional[List[str]] = None
    aliases: Optional[List[str]] = None


class Inventory(BaseModel):
    elements: Dict[str, InventoryElement] = Field(default_factory=dict)
    nets: List[str] = Field(default_factory=list)
    blocks: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    def all_ids(self) -> List[str]:
        ids = list(self.elements.keys()) + list(self.blocks.keys()) + list(self.nets)
        return sorted(set(ids))

    def alias_map(self) -> Dict[str, str]:
        amap: Dict[str, str] = {}
        for k, el in self.elements.items():
            amap[k] = k
            if el.aliases:
                for a in el.aliases:
                    amap[a] = k
        for b in self.blocks.keys():
            amap[b] = b
        for n in self.nets:
            amap[n] = n
        return amap


class RubricCriterion(BaseModel):
    id: str
    desc: str
    required: bool = False
    # Optional: restrict pattern matching to a named markdown section (case-insensitive)
    section: Optional[str] = None
    patterns_any: Optional[List[str]] = None
    patterns_all: Optional[List[str]] = None
    min_any: Optional[int] = None
    anti_patterns: Optional[List[str]] = None
    requires_grounding: bool = False
    min_refs: Optional[int] = None
    weight: float = 0.0
    penalty_missing_ok: bool = False


class Rubric(BaseModel):
    rubric_id: str
    version: str
    weights: Dict[str, float]
    criteria: List[RubricCriterion]
    scoring: Dict[str, float]


class Question(BaseModel):
    id: str
    track: str
    modality: str
    artifact_path: str
    rubric_id: str
    rubric_path: str
    prompt_template: str
    require_sections: List[str]
    answer_format: str
    meta: Dict[str, Any] = Field(default_factory=dict)


class EvalItem(BaseModel):
    item_dir: str
    inventory: Inventory
    questions: List[Question]

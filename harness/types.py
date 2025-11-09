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


# Legacy rubric models removed: LLM-as-judge only


class Question(BaseModel):
    id: str
    track: str
    modality: str
    artifact_path: str
    prompt_template: str
    judge_prompt: str
    judge_id: str
    require_sections: List[str]
    answer_format: str
    meta: Dict[str, Any] = Field(default_factory=dict)
    verification: Optional[Dict[str, Any]] = None  # For SPICE verification
    attachments: List[Dict[str, str]] = Field(default_factory=list)  # For Gm/ID tables, templates
    prompt_path: Optional[str] = None  # Alternative to prompt_template


class EvalItem(BaseModel):
    item_dir: str
    inventory: Inventory
    questions: List[Question]

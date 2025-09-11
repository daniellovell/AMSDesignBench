from __future__ import annotations
from typing import Any, Dict, List
from .base import BaseAdapter


TEMPLATE = """### Topology
single-stage (uncertain); treating as differential pair with mirror load.

### Assumptions
- single dominant pole; unity-gain context; external CL

### Key relation
GBW ≈ gm/CL under the above assumptions.

### Grounded evidence
- cites: {cite1}, {cite2}

### Answer
GBW is set by gm/CL; exceptions like feedforward/current-steering change the relation. CMFB loop should be slower and compensated at its amp when present.
"""


class DummyAdapter(BaseAdapter):
    name = "dummy"

    def predict(self, batch: List[Dict[str, Any]]) -> List[str]:
        outs: List[str] = []
        for item in batch:
            inv_ids = item.get("inventory_ids", [])
            cite1 = inv_ids[0] if inv_ids else "M1"
            cite2 = inv_ids[1] if len(inv_ids) > 1 else "CL"
            outs.append(TEMPLATE.format(cite1=f"`{cite1}`", cite2=f"`{cite2}`"))
        return outs


def build() -> DummyAdapter:
    return DummyAdapter()

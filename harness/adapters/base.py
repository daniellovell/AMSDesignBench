from __future__ import annotations
from typing import Any, Dict, List


class BaseAdapter:
    name: str = "base"

    def predict(self, batch: List[Dict[str, Any]]) -> List[str]:
        raise NotImplementedError


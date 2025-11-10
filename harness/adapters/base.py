from __future__ import annotations
from typing import Any, Dict, List


class BaseAdapter:
    name: str = "base"

    def predict(self, batch: List[Dict[str, Any]]) -> List[str]:
        """
        Batch prediction method for benchmark evaluation.
        
        Args:
            batch: List of dictionaries with question context
            
        Returns:
            List of string predictions
        """
        raise NotImplementedError
    
    def generate(self, prompt: str, **kwargs) -> str:
        """
        Single-shot generation method for direct LLM calls.
        
        Args:
            prompt: Text prompt for the LLM
            **kwargs: Additional generation parameters
            
        Returns:
            Generated text response
        """
        # Default implementation wraps predict
        result = self.predict([{"prompt": prompt}])
        return result[0] if result else ""


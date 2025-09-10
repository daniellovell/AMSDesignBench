from __future__ import annotations
import os
from typing import Any, Dict, List
from .base import BaseAdapter

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


SYS_PROMPT = (
    "You are an expert analog/mixed-signal IC designer. "
    "Follow the user's Required sections exactly and return markdown only."
)


class OpenAIAdapter(BaseAdapter):
    name = "openai"

    def __init__(self, model: str | None = None, temperature: float = 0.2, max_tokens: int = 800):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", temperature))
        self.max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", max_tokens))
        if OpenAI is None:
            raise RuntimeError("openai package not installed. pip install openai")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY env var not set.")
        self.client = OpenAI(api_key=self.api_key)

    def predict(self, batch: List[Dict[str, Any]]) -> List[str]:
        outs: List[str] = []
        for item in batch:
            prompt = item.get("prompt", "")
            inv_ids = item.get("inventory_ids", [])
            question = item.get("question", {})
            req_sections = question.get("require_sections", [])
            modality = question.get("modality", "")
            artifact_path = item.get("artifact_path", "")

            user = (
                f"Artifact modality: {modality}. Artifact path: {artifact_path}.\n"
                f"Inventory IDs you may cite: {', '.join(inv_ids)}\n"
                f"Required sections: {', '.join(req_sections)}\n\n"
                f"{prompt}\n"
            )

            resp = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": SYS_PROMPT},
                    {"role": "user", "content": user},
                ],
            )
            text = resp.choices[0].message.content or ""
            outs.append(text)
        return outs


def build(model: str | None = None, temperature: float | None = None, max_tokens: int | None = None) -> OpenAIAdapter:
    kwargs = {}
    if model is not None:
        kwargs["model"] = model
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return OpenAIAdapter(**kwargs)

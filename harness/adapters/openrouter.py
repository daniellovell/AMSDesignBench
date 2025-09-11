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


class OpenRouterAdapter(BaseAdapter):
    name = "openrouter"

    def __init__(self, model: str | None = None, temperature: float = 0.2, max_tokens: int = 800):
        if OpenAI is None:
            raise RuntimeError("openai package not installed. pip install openai")
        self.model = model or os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY env var not set.")
        self.temperature = float(os.getenv("OPENROUTER_TEMPERATURE", temperature))
        self.max_tokens = int(os.getenv("OPENROUTER_MAX_TOKENS", max_tokens))
        headers: Dict[str, str] = {}
        ref = os.getenv("OPENROUTER_REFERER")
        title = os.getenv("OPENROUTER_TITLE")
        if ref:
            headers["HTTP-Referer"] = ref
        if title:
            headers["X-Title"] = title
        self.client = OpenAI(api_key=self.api_key, base_url="https://openrouter.ai/api/v1", default_headers=headers or None)

    def predict(self, batch: List[Dict[str, Any]]) -> List[str]:
        outs: List[str] = []
        for item in batch:
            prompt = item.get("prompt", "")
            inv_ids = item.get("inventory_ids", [])
            question = item.get("question", {})
            req_sections = question.get("require_sections", [])
            modality = question.get("modality", "")
            artifact_path = item.get("artifact_path", "")

            artifact = item.get("artifact", "")
            art_block = f"\nArtifact ({modality}):\n```spice\n{artifact}\n```\n" if artifact else "\n"
            user = (
                f"Artifact modality: {modality}. Artifact path: {artifact_path}.\n"
                f"Inventory IDs you may cite: {', '.join(inv_ids)}\n"
                f"Required sections: {', '.join(req_sections)}\n"
                f"{art_block}\n"
                f"{prompt}\n"
            )

            params: Dict[str, Any] = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYS_PROMPT},
                    {"role": "user", "content": user},
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            # Similar adaptations as OpenAI adapter for reasoning models
            if "gpt-5" in str(self.model).lower():
                params.pop("max_tokens", None)
                params.pop("temperature", None)
            for _ in range(3):
                try:
                    resp = self.client.chat.completions.create(**params)
                    break
                except Exception as e:
                    emsg = str(getattr(e, "message", e))
                    txt = (emsg or str(e)).lower()
                    adapted = False
                    if "max_tokens" in txt and "max_completion_tokens" in txt:
                        params.pop("max_tokens", None)
                        params["max_completion_tokens"] = self.max_tokens
                        adapted = True
                    if "temperature" in txt and ("unsupported" in txt or "does not support" in txt or "only the default" in txt):
                        params.pop("temperature", None)
                        adapted = True
                    if not adapted:
                        raise
            text = (getattr(resp.choices[0].message, "content", None) or "").strip()
            outs.append(text)
        return outs


def build(model: str | None = None, temperature: float | None = None, max_tokens: int | None = None) -> OpenRouterAdapter:
    kwargs: Dict[str, Any] = {}
    if model is not None:
        kwargs["model"] = model
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return OpenRouterAdapter(**kwargs)


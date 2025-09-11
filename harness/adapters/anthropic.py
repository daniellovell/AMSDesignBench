from __future__ import annotations
import os
from typing import Any, Dict, List
from .base import BaseAdapter

try:
    import anthropic  # type: ignore
except Exception:  # pragma: no cover
    anthropic = None  # type: ignore


SYS_PROMPT = (
    "You are an expert analog/mixed-signal IC designer. "
    "Follow the user's Required sections exactly and return markdown only."
)


class AnthropicAdapter(BaseAdapter):
    name = "anthropic"

    def __init__(self, model: str | None = None, temperature: float = 0.2, max_tokens: int = 800):
        if anthropic is None:
            raise RuntimeError("anthropic package not installed. pip install anthropic")
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY env var not set.")
        self.temperature = float(os.getenv("ANTHROPIC_TEMPERATURE", temperature))
        self.max_tokens = int(os.getenv("ANTHROPIC_MAX_TOKENS", max_tokens))
        self.client = anthropic.Anthropic(api_key=self.api_key)

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

            # Build Anthropic request; adapt to potential param name changes.
            params: Dict[str, Any] = {
                "model": self.model,
                "system": SYS_PROMPT,
                "messages": [{"role": "user", "content": [{"type": "text", "text": user}]}],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }

            # Attempt a couple adaptive retries for temperature-only restrictions.
            for _ in range(2):
                try:
                    resp = self.client.messages.create(**params)  # type: ignore[arg-type]
                    break
                except Exception as e:
                    msg = (str(getattr(e, "message", e)) or str(e)).lower()
                    adapted = False
                    if "temperature" in msg and ("unsupported" in msg or "does not support" in msg or "only the default" in msg):
                        params.pop("temperature", None)
                        adapted = True
                    if not adapted:
                        raise

            # Extract text blocks
            text = ""
            try:
                parts = getattr(resp, "content", [])  # type: ignore[name-defined]
                if isinstance(parts, list):
                    for p in parts:
                        if getattr(p, "type", None) == "text":
                            t = getattr(p, "text", "")
                            if t:
                                text += t
            except Exception:
                text = ""
            outs.append(text.strip())
        return outs


def build(model: str | None = None, temperature: float | None = None, max_tokens: int | None = None) -> AnthropicAdapter:
    kwargs: Dict[str, Any] = {}
    if model is not None:
        kwargs["model"] = model
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return AnthropicAdapter(**kwargs)

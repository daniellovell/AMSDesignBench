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
    "NEVER use LaTeX or MathJax in your responses."
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

            artifact = item.get("artifact", "")
            art_block = f"\nArtifact ({modality}):\n```spice\n{artifact}\n```\n" if artifact else "\n"
            user = (
                f"Artifact modality: {modality}. Artifact path: {artifact_path}.\n"
                f"Inventory IDs you may cite: {', '.join(inv_ids)}\n"
                f"Required sections: {', '.join(req_sections)}\n"
                f"{art_block}\n"
                f"{prompt}\n"
            )

            # Build a flexible params dict and adapt on common OpenAI param errors.
            params: Dict[str, Any] = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYS_PROMPT},
                    {"role": "user", "content": user},
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            # gpt-5 family can consume the entire completion budget as reasoning
            # and return empty text when a hard cap is set. Prefer no cap.
            if "gpt-5" in str(self.model).lower():
                params.pop("max_tokens", None)
                # Temperature typically unsupported for gpt-5; let default apply
                params.pop("temperature", None)
            # Some models (gpt-5 family) only support default temperature; retry without it.
            # Some models require max_completion_tokens instead of max_tokens.
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
            # Extract text; if empty, fall back to Responses API for newer models
            text = (getattr(resp.choices[0].message, "content", None) or "").strip()
            if not text:
                try:
                    r2 = self.client.responses.create(
                        model=self.model,
                        instructions=SYS_PROMPT,
                        input=user,
                        max_output_tokens=self.max_tokens,
                    )
                    text = (getattr(r2, "output_text", None) or "").strip()
                    if not text:
                        # Attempt structured extraction
                        try:
                            d = r2.model_dump()  # type: ignore[attr-defined]
                        except Exception:
                            d = {}
                        # Look for output.content[...].text
                        out_list = d.get("output") or d.get("outputs") or []
                        if isinstance(out_list, list):
                            for out in out_list:
                                cont = (out or {}).get("content") or []
                                if isinstance(cont, list):
                                    for part in cont:
                                        t = part.get("text") or part.get("content")
                                        if isinstance(t, str) and t.strip():
                                            text = t.strip()
                                            break
                                    if text:
                                        break
                except Exception:
                    # Keep text as empty if Responses API is unavailable/unsupported
                    pass
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

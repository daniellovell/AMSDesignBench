from __future__ import annotations
import os
from typing import Any, Dict, List
import time
from time import perf_counter
import random as _rnd
import re
from .base import BaseAdapter
from ..utils.rate_limiter import get_limiter
from ..utils import profiling

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


SYS_PROMPT = (
    "You are an expert analog/mixed-signal IC designer. "
    "Follow the user's Required sections exactly and return markdown only."
    "NEVER use LaTeX or MathJax in your responses."
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
            def _display_modality(mod: str) -> str:
                m = (mod or "").strip()
                if m == "cascode":
                    return "analog description language"
                if m == "spice_netlist":
                    return "SPICE netlist"
                if m == "casIR":
                    return "casIR"
                return m or "artifact"

            artifact = item.get("artifact", "")
            disp_mod = _display_modality(modality)
            fence = "spice" if modality == "spice_netlist" else ("json" if modality == "casIR" else "text")
            art_block = f"\nArtifact ({disp_mod}):\n```{fence}\n{artifact}\n```\n" if artifact else "\n"
            user = (
                f"Artifact modality: {disp_mod}.\n"
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
            # Cross-thread rate limiting
            try:
                # Estimate tokens as chars/4 for system+user plus completion budget
                est = int((len(SYS_PROMPT) + len(user)) / float(os.getenv("OPENROUTER_TOKEN_DIVISOR", 4))) + int(self.max_tokens)
                rpm = float(os.getenv("OPENROUTER_RPM", 0) or 0)
                tpm = float(os.getenv("OPENROUTER_TPM", 0) or 0)
                if rpm > 0 or tpm > 0:
                    get_limiter("openrouter", rpm=rpm, tpm=tpm).acquire(
                        token_cost=est,
                        req_cost=1.0,
                        enable_profiling=profiling.is_enabled(),
                    )
            except Exception:
                pass
            # Similar adaptations as OpenAI adapter for reasoning models
            if "gpt-5" in str(self.model).lower():
                params.pop("max_tokens", None)
                params.pop("temperature", None)
            # Parameter adaptation + robust backoff for rate limits/overload
            def _parse_retry_after(msg: str) -> float:
                m = re.search(r"try again in\s*([0-9]+\.?[0-9]*)s", msg, flags=re.I)
                if m:
                    try:
                        return float(m.group(1))
                    except Exception:
                        return 0.0
                return 0.0
            max_attempts = int(os.getenv("OPENROUTER_MAX_RETRIES", 8))
            base_delay = float(os.getenv("OPENROUTER_BACKOFF_BASE", 1.0))
            attempt = 0
            while attempt < max_attempts:
                attempt += 1
                try:
                    api_timer = perf_counter() if profiling.is_enabled() else None
                    resp = self.client.chat.completions.create(**params)
                    if api_timer is not None:
                        profiling.log(
                            "api",
                            "call",
                            (perf_counter() - api_timer) * 1000,
                            context=f"adapter={self.name} model={self.model}",
                        )
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
                    if adapted:
                        continue
                    is_rate = ("rate limit" in txt) or ("429" in txt) or ("tpm" in txt) or ("rpm" in txt)
                    is_overload = ("service unavailable" in txt) or ("overloaded" in txt) or ("temporarily" in txt) or ("timeout" in txt)
                    if is_rate or is_overload:
                        parsed = _parse_retry_after(emsg)
                        delay = parsed if parsed > 0 else (base_delay * (2 ** (attempt - 1)))
                        delay += _rnd.uniform(0.1, 0.5)
                        time.sleep(min(delay, 20.0))
                        continue
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


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
    import anthropic  # type: ignore
except Exception:  # pragma: no cover
    anthropic = None  # type: ignore


SYS_PROMPT = (
    "You are an expert analog/mixed-signal IC designer. "
    "Follow the user's Required sections exactly and return markdown only."
    "NEVER use LaTeX or MathJax in your responses."
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

            # Build Anthropic request; adapt to potential param name changes.
            params: Dict[str, Any] = {
                "model": self.model,
                "system": SYS_PROMPT,
                "messages": [{"role": "user", "content": [{"type": "text", "text": user}]}],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            # Cross-thread rate limiting
            try:
                est = int((len(SYS_PROMPT) + len(user)) / float(os.getenv("ANTHROPIC_TOKEN_DIVISOR", 4))) + int(self.max_tokens)
                rpm = float(os.getenv("ANTHROPIC_RPM", 0) or 0)
                tpm = float(os.getenv("ANTHROPIC_TPM", 0) or 0)
                if rpm > 0 or tpm > 0:
                    get_limiter("anthropic", rpm=rpm, tpm=tpm).acquire(
                        token_cost=est,
                        req_cost=1.0,
                        enable_profiling=profiling.is_enabled(),
                    )
            except Exception:
                pass

            # Adaptive retries + exponential backoff for rate/overload
            def _parse_retry_after(msg: str) -> float:
                m = re.search(r"try again in\s*([0-9]+\.?[0-9]*)s", msg, flags=re.I)
                if m:
                    try:
                        return float(m.group(1))
                    except Exception:
                        return 0.0
                return 0.0
            max_attempts = int(os.getenv("ANTHROPIC_MAX_RETRIES", 8))
            base_delay = float(os.getenv("ANTHROPIC_BACKOFF_BASE", 1.0))
            attempt = 0
            while attempt < max_attempts:
                attempt += 1
                try:
                    api_timer = perf_counter() if profiling.is_enabled() else None
                    resp = self.client.messages.create(**params)  # type: ignore[arg-type]
                    if api_timer is not None:
                        profiling.log(
                            "api",
                            "call",
                            (perf_counter() - api_timer) * 1000,
                            context=f"adapter={self.name} model={self.model}",
                        )
                    break
                except Exception as e:
                    msg = (str(getattr(e, "message", e)) or str(e)).lower()
                    adapted = False
                    if "temperature" in msg and ("unsupported" in msg or "does not support" in msg or "only the default" in msg):
                        params.pop("temperature", None)
                        adapted = True
                    if adapted:
                        continue
                    is_rate = ("rate limit" in msg) or ("429" in msg)
                    is_overload = ("service unavailable" in msg) or ("overloaded" in msg) or ("temporarily" in msg) or ("timeout" in msg)
                    if is_rate or is_overload:
                        parsed = _parse_retry_after(msg)
                        delay = parsed if parsed > 0 else (base_delay * (2 ** (attempt - 1)))
                        delay += _rnd.uniform(0.1, 0.5)
                        time.sleep(min(delay, 20.0))
                        continue
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

from __future__ import annotations
import os
from typing import Any, Dict, List
import time
import random as _rnd
import re
from .base import BaseAdapter
from ..utils.rate_limiter import get_limiter

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
            # Cross-thread rate limiting (approximate token count)
            try:
                # Estimate tokens as chars/4 for system+user plus completion budget
                est = int((len(SYS_PROMPT) + len(user)) / float(os.getenv("OPENAI_TOKEN_DIVISOR", 4))) + int(self.max_tokens)
                rpm = float(os.getenv("OPENAI_RPM", 0) or 0)
                tpm = float(os.getenv("OPENAI_TPM", 0) or 0)
                if rpm > 0 or tpm > 0:
                    get_limiter("openai", rpm=rpm, tpm=tpm).acquire(token_cost=est, req_cost=1.0)
            except Exception:
                pass
            # gpt-5 family can consume the entire completion budget as reasoning
            # and return empty text when a hard cap is set. Prefer no cap.
            if "gpt-5" in str(self.model).lower():
                params.pop("max_tokens", None)
                # Temperature typically unsupported for gpt-5; let default apply
                params.pop("temperature", None)
            # Some models (gpt-5 family) only support default temperature; retry without it.
            # Some models require max_completion_tokens instead of max_tokens.
            # Add robust backoff handling for transient errors/rate limits.
            def _parse_retry_after(msg: str) -> float:
                # Try to capture "try again in Xs" pattern
                m = re.search(r"try again in\s*([0-9]+\.?[0-9]*)s", msg, flags=re.I)
                if m:
                    try:
                        return float(m.group(1))
                    except Exception:
                        pass
                return 0.0

            max_attempts = int(os.getenv("OPENAI_MAX_RETRIES", 8))
            base_delay = float(os.getenv("OPENAI_BACKOFF_BASE", 1.0))
            attempt = 0
            last_exc: Exception | None = None
            while attempt < max_attempts:
                attempt += 1
                # Parameter adaptation loop
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
                            last_exc = e
                            break
                else:
                    last_exc = RuntimeError("parameter adaptation failed")
                if last_exc is None and 'resp' in locals():
                    # Success
                    break
                # Transient/Rate limit handling
                err_txt = str(getattr(last_exc, 'message', last_exc) or '').lower()
                is_rate = ("rate limit" in err_txt) or ("429" in err_txt) or ("tpm" in err_txt) or ("rpm" in err_txt)
                is_overload = ("service unavailable" in err_txt) or ("overloaded" in err_txt) or ("temporarily" in err_txt) or ("timeout" in err_txt)
                if is_rate or is_overload:
                    # Compute delay: try parse, else exponential backoff with jitter
                    parsed = _parse_retry_after(str(getattr(last_exc, 'message', last_exc) or ''))
                    delay = parsed if parsed > 0 else (base_delay * (2 ** (attempt - 1)))
                    delay += _rnd.uniform(0.1, 0.5)
                    time.sleep(min(delay, 20.0))
                    last_exc = None
                    continue
                # Not recoverable
                raise last_exc
            if last_exc is not None:
                raise last_exc
            # Extract text; if empty, fall back to Responses API for newer models
            text = (getattr(resp.choices[0].message, "content", None) or "").strip()
            if not text:
                # Try Responses API with the same backoff strategy
                attempt = 0
                last_exc = None
                while attempt < max_attempts and not text:
                    attempt += 1
                    try:
                        r2 = self.client.responses.create(
                            model=self.model,
                            instructions=SYS_PROMPT,
                            input=user,
                            max_output_tokens=self.max_tokens,
                        )
                        text = (getattr(r2, "output_text", None) or "").strip()
                        if not text:
                            try:
                                d = r2.model_dump()  # type: ignore[attr-defined]
                            except Exception:
                                d = {}
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
                        break
                    except Exception as e:
                        last_exc = e
                        err_txt = str(getattr(e, 'message', e) or '').lower()
                        is_rate = ("rate limit" in err_txt) or ("429" in err_txt) or ("tpm" in err_txt) or ("rpm" in err_txt)
                        is_overload = ("service unavailable" in err_txt) or ("overloaded" in err_txt) or ("temporarily" in err_txt) or ("timeout" in err_txt)
                        if is_rate or is_overload:
                            parsed = _parse_retry_after(str(getattr(e, 'message', e) or ''))
                            delay = parsed if parsed > 0 else (base_delay * (2 ** (attempt - 1)))
                            delay += _rnd.uniform(0.1, 0.5)
                            time.sleep(min(delay, 20.0))
                            continue
                        else:
                            break
                # If still empty, leave as-is (will be scored as zero)
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

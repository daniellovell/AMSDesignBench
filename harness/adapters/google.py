from __future__ import annotations
import os
from typing import Any, Dict, List
import time
import random as _rnd
import re
from .base import BaseAdapter
from ..utils.rate_limiter import get_limiter

try:
    from google import genai  # type: ignore
except Exception:  # pragma: no cover
    genai = None  # type: ignore


SYS_PROMPT = (
    "You are an expert analog/mixed-signal IC designer. "
    "Follow the user's Required sections exactly and return markdown only."
    "NEVER use LaTeX or MathJax in your responses."
)


class GoogleAdapter(BaseAdapter):
    name = "google"

    def __init__(self, model: str | None = None, temperature: float = 0.2, max_tokens: int = 800):
        if genai is None:
            raise RuntimeError("google-genai package not installed. pip install google-genai")
        self.model = model or os.getenv("GOOGLE_MODEL", "gemini-2.5-pro")
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise RuntimeError("GOOGLE_API_KEY env var not set.")
        self.temperature = float(os.getenv("GOOGLE_TEMPERATURE", temperature))
        self.max_tokens = int(os.getenv("GOOGLE_MAX_TOKENS", max_tokens))
        self.client = genai.Client(api_key=self.api_key)

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

            # Build Google Gemini request
            # Combine system prompt and user content
            full_content = f"{SYS_PROMPT}\n\n{user}"
            
            params: Dict[str, Any] = {
                "model": self.model,
                "contents": full_content,
            }
            
            # Add generation parameters directly (not in a config dict)
            if self.temperature is not None:
                params["temperature"] = self.temperature
            if self.max_tokens is not None:
                params["max_output_tokens"] = self.max_tokens
            
            # Cross-thread rate limiting
            try:
                est = int((len(SYS_PROMPT) + len(user)) / float(os.getenv("GOOGLE_TOKEN_DIVISOR", 4))) + int(self.max_tokens)
                rpm = float(os.getenv("GOOGLE_RPM", 0) or 0)
                tpm = float(os.getenv("GOOGLE_TPM", 0) or 0)
                if rpm > 0 or tpm > 0:
                    get_limiter("google", rpm=rpm, tpm=tpm).acquire(token_cost=est, req_cost=1.0)
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
            
            max_attempts = int(os.getenv("GOOGLE_MAX_RETRIES", 8))
            base_delay = float(os.getenv("GOOGLE_BACKOFF_BASE", 1.0))
            attempt = 0
            last_exc: Exception | None = None
            
            while attempt < max_attempts:
                attempt += 1
                # Parameter adaptation loop
                for _ in range(3):
                    try:
                        resp = self.client.models.generate_content(**params)
                        break
                    except Exception as e:
                        emsg = str(getattr(e, "message", e))
                        txt = (emsg or str(e)).lower()
                        adapted = False
                        # Handle "unexpected keyword argument" errors - remove the parameter entirely
                        if "unexpected keyword argument" in txt:
                            if "temperature" in txt and "temperature" in params:
                                params.pop("temperature", None)
                                adapted = True
                            elif "max_output_tokens" in txt and "max_output_tokens" in params:
                                params.pop("max_output_tokens", None)
                                adapted = True
                        # Handle other parameter errors
                        elif "temperature" in txt or "max_output_tokens" in txt:
                            if "temperature" in txt and ("unsupported" in txt or "does not support" in txt or "only the default" in txt):
                                params.pop("temperature", None)
                                adapted = True
                            if "max_output_tokens" in txt and ("unsupported" in txt or "does not support" in txt):
                                params.pop("max_output_tokens", None)
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
                is_rate = ("rate limit" in err_txt) or ("429" in err_txt) or ("tpm" in err_txt) or ("rpm" in err_txt) or ("quota" in err_txt)
                is_overload = ("service unavailable" in err_txt) or ("overloaded" in err_txt) or ("temporarily" in err_txt) or ("timeout" in err_txt) or ("503" in err_txt)
                
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
            
            # Extract text from response
            text = ""
            try:
                # Try direct text attribute first
                text = getattr(resp, "text", None) or ""
                if not text:
                    # Try accessing response structure
                    if hasattr(resp, "candidates") and resp.candidates:
                        candidate = resp.candidates[0]
                        if hasattr(candidate, "content") and candidate.content:
                            if hasattr(candidate.content, "parts"):
                                for part in candidate.content.parts:
                                    if hasattr(part, "text"):
                                        text += part.text or ""
                if not text:
                    # Log warning if we got empty response
                    import sys
                    print(f"[WARN] Google adapter got empty response. Response object: {resp}", file=sys.stderr, flush=True)
                    # Try to extract any diagnostic info
                    try:
                        if hasattr(resp, '__dict__'):
                            print(f"[WARN] Response attributes: {resp.__dict__}", file=sys.stderr, flush=True)
                    except Exception:
                        pass
            except Exception as e:
                import sys
                print(f"[ERROR] Failed to extract text from Google response: {e}", file=sys.stderr, flush=True)
                text = ""
            
            outs.append(text.strip())
        return outs


def build(model: str | None = None, temperature: float | None = None, max_tokens: int | None = None) -> GoogleAdapter:
    kwargs: Dict[str, Any] = {}
    if model is not None:
        kwargs["model"] = model
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return GoogleAdapter(**kwargs)


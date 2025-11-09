from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
import time
from time import perf_counter
import random as _rnd
import re
from .base import BaseAdapter
from ..utils.rate_limiter import get_limiter
from ..utils import profiling

try:
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
    try:
        from google.genai.types import HttpOptions  # type: ignore
    except ImportError:
        HttpOptions = None  # type: ignore
except Exception:  # pragma: no cover
    genai = None  # type: ignore
    types = None  # type: ignore
    HttpOptions = None  # type: ignore


SYS_PROMPT = (
    "You are an expert analog/mixed-signal IC designer. "
    "Follow the user's Required sections exactly and return markdown only."
    "NEVER use LaTeX or MathJax in your responses."
)


class GoogleAdapter(BaseAdapter):
    name = "google"

    def __init__(self, model: str | None = None, temperature: float = 0.2, max_tokens: int = 800):
        """Configure the Gemini client used for every request."""
        if genai is None:
            raise RuntimeError("google-genai package not installed. pip install google-genai")
        self.model = model or os.getenv("GOOGLE_MODEL", "gemini-2.5-pro")
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise RuntimeError("GOOGLE_API_KEY env var not set.")
        self.temperature = float(os.getenv("GOOGLE_TEMPERATURE", temperature))
        self.max_tokens = int(os.getenv("GOOGLE_MAX_TOKENS", max_tokens))
        timeout_seconds = float(os.getenv("GOOGLE_TIMEOUT", "60.0"))
        # Initialize client with timeout via HttpOptions if available
        client_kwargs: Dict[str, Any] = {"api_key": self.api_key}
        if HttpOptions is not None:
            # Timeout in HttpOptions is in milliseconds
            timeout_ms = int(timeout_seconds * 1000)
            client_kwargs["http_options"] = HttpOptions(timeout=timeout_ms)
        self.client = genai.Client(**client_kwargs)

    def predict(self, batch: List[Dict[str, Any]]) -> List[str]:
        """Render prompts, call Gemini, and return plain-text completions."""
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

            contents = self._build_user_contents(user)
            config = self._build_generation_config()

            params: Dict[str, Any] = {
                "model": self.model,
                "contents": contents,
            }
            if config is not None:
                params["config"] = config
            
            # Cross-thread rate limiting
            try:
                est = int((len(SYS_PROMPT) + len(user)) / float(os.getenv("GOOGLE_TOKEN_DIVISOR", 4))) + int(self.max_tokens)
                rpm = float(os.getenv("GOOGLE_RPM", 0) or 0)
                tpm = float(os.getenv("GOOGLE_TPM", 0) or 0)
                if rpm > 0 or tpm > 0:
                    get_limiter("google", rpm=rpm, tpm=tpm).acquire(
                        token_cost=est,
                        req_cost=1.0,
                        enable_profiling=profiling.is_enabled(),
                    )
            except Exception:
                pass

            resp = self._call_with_retry(params)
            
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

    def _build_user_contents(self, user_text: str) -> List[Any]:
        """Return the user message structure expected by the Google SDK."""
        if types is None:
            return [{"role": "user", "parts": [{"text": user_text}]}]
        return [types.Content(role="user", parts=[types.Part(text=user_text)])]

    def _build_system_instruction(self) -> Optional[Any]:
        """Wrap the benchmark system prompt in the SDK's content object."""
        if not SYS_PROMPT:
            return None
        if types is None:
            return {"role": "system", "parts": [{"text": SYS_PROMPT}]}
        return types.Content(role="system", parts=[types.Part(text=SYS_PROMPT)])

    def _build_thinking_config(self, budget: int) -> Optional[Any]:
        """Create the thinking configuration block when supported."""
        if types is None:
            return {"thinking_budget": budget}
        return types.ThinkingConfig(thinking_budget=budget)

    def _build_generation_config(self) -> Optional[Any]:
        """Assemble the final GenerateContentConfig with knobs we expose."""
        thinking_budget = int(os.getenv("GOOGLE_THINKING_BUDGET", "0"))
        config_kwargs: Dict[str, Any] = {}
        if self.temperature is not None:
            config_kwargs["temperature"] = self.temperature
        if self.max_tokens is not None:
            config_kwargs["max_output_tokens"] = self.max_tokens
        system_instruction = self._build_system_instruction()
        if system_instruction is not None:
            config_kwargs["system_instruction"] = system_instruction
        config_kwargs["thinking_config"] = self._build_thinking_config(thinking_budget)

        if not config_kwargs:
            return None
        if types is None:
            return config_kwargs
        return types.GenerateContentConfig(**config_kwargs)

    def _call_with_retry(self, params: Dict[str, Any]) -> Any:
        """Invoke the API with lightweight retry logic for transient faults."""
        max_attempts = int(os.getenv("GOOGLE_MAX_RETRIES", 8))
        base_delay = float(os.getenv("GOOGLE_BACKOFF_BASE", 1.0))
        attempt = 0
        last_exc: Optional[Exception] = None

        while attempt < max_attempts:
            attempt += 1
            try:
                api_timer = perf_counter() if profiling.is_enabled() else None
                resp = self.client.models.generate_content(**params)
                if api_timer is not None:
                    profiling.log(
                        "api",
                        "call",
                        (perf_counter() - api_timer) * 1000,
                        context=f"adapter={self.name} model={self.model}",
                    )
                return resp
            except Exception as exc:  # pragma: no cover - retry paths tested indirectly
                last_exc = exc
                err_txt = str(getattr(exc, "message", exc) or "").lower()
                is_rate, is_timeout, is_overload = self._classify_retryable_error(err_txt)
                if not (is_rate or is_timeout or is_overload):
                    raise
                delay = self._compute_retry_delay(exc, attempt, base_delay, is_timeout)
                time.sleep(delay)

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("google adapter failed without response")

    @staticmethod
    def _classify_retryable_error(err_txt: str) -> tuple[bool, bool, bool]:
        """Classify an error message into rate/time/overload buckets."""
        is_rate = ("rate limit" in err_txt) or ("429" in err_txt) or ("tpm" in err_txt) or ("rpm" in err_txt) or ("quota" in err_txt)
        is_timeout = ("timeout" in err_txt) or ("timed out" in err_txt) or ("deadline exceeded" in err_txt)
        is_overload = ("service unavailable" in err_txt) or ("overloaded" in err_txt) or ("temporarily" in err_txt) or ("503" in err_txt)
        return is_rate, is_timeout, is_overload

    def _compute_retry_delay(self, exc: Exception, attempt: int, base_delay: float, is_timeout: bool) -> float:
        """Derive the backoff delay for the current retry attempt."""
        parsed = self._parse_retry_after(str(getattr(exc, "message", exc) or ""))
        if parsed > 0:
            return min(parsed, 10.0 if is_timeout else 20.0)
        delay = base_delay * (2 ** (attempt - 1))
        delay += _rnd.uniform(0.1, 0.5)
        return min(delay, 10.0 if is_timeout else 20.0)

    @staticmethod
    def _parse_retry_after(msg: str) -> float:
        """Extract a server-specified retry-after hint when present."""
        m = re.search(r"try again in\s*([0-9]+\.?[0-9]*)s", msg, flags=re.I)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                return 0.0
        return 0.0


def build(model: str | None = None, temperature: float | None = None, max_tokens: int | None = None) -> GoogleAdapter:
    kwargs: Dict[str, Any] = {}
    if model is not None:
        kwargs["model"] = model
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return GoogleAdapter(**kwargs)


from __future__ import annotations
import json
import os
from typing import Any, Dict, Optional
import time
from time import perf_counter
import random as _rnd
import re
import traceback
from ..utils.rate_limiter import get_limiter, _LIMITERS, _LIM_LOCK
import threading
import os as _os
import sys as _sys
from ..utils import profiling

try:
    from openai import OpenAI, APITimeoutError
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore
    APITimeoutError = TimeoutError  # fallback to built-in if import fails


def _client() -> Optional[Any]:
    if OpenAI is None:
        return None
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    # Add timeout to prevent hanging (default 60s, configurable via env)
    timeout_seconds = float(os.getenv("OPENAI_TIMEOUT", "60.0"))
    return OpenAI(api_key=api_key, timeout=timeout_seconds)


_SEM: threading.Semaphore | None = None
_DETECTED_TPM: float | None = None
_DETECTED_TPM_LOCK = threading.Lock()


def _sem() -> threading.Semaphore:
    """
    Return the module-wide semaphore that controls judge concurrency.
    
    Reads the environment variable OPENAI_JUDGE_CONCURRENCY and creates a singleton threading.Semaphore sized to that value if it is a positive integer; otherwise creates a semaphore with a default count of 3. Subsequent calls return the same semaphore instance.
    
    Returns:
        threading.Semaphore: The module-global semaphore used to limit concurrent judge operations.
    """
    global _SEM
    if _SEM is None:
        try:
            lim = int(_os.getenv("OPENAI_JUDGE_CONCURRENCY", "0") or "0")
        except Exception:
            lim = 0
        if lim and lim > 0:
            _SEM = threading.Semaphore(lim)
        else:
            # Default to conservative concurrency if unset
            _SEM = threading.Semaphore(3)
    return _SEM


def judge_answer(
    answer_to_evaluate: str,
    rubric_markdown: str,
    track: str,
    inventory: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Evaluate an answer against a Markdown rubric using an OpenAI-based grading judge and return the parsed scoring result.
    
    Sends the rubric, answer, and optional inventory context to an OpenAI model (chat or Responses API depending on model), applies retries, rate-limiting, and parameter adaptation as needed, and parses the model's JSON output.
    
    Parameters:
        answer_to_evaluate (str): The answer text to be judged.
        rubric_markdown (str): The rubric in Markdown that the judge should use to score the answer.
        track (str): Evaluation track label (e.g., "design", "analysis", "debugging") used to shape the system prompt.
        inventory (Optional[Dict[str, Any]]): Optional contextual information to include in the evaluation payload.
        model (Optional[str]): Optional model identifier to override environment-configured judge model.
    
    Returns:
        Optional[Dict[str, Any]]: On success, a dict parsed from the judge's JSON output containing at minimum a "scores" key and an attached "debug" field. On failure, a dict with an "error" message and often a "debug" payload and/or "raw" text for diagnosis. Returns None only in unexpected runtime scenarios.
    """
    client = _client()
    if client is None:
        print("[JUDGE] OpenAI client not configured (set OPENAI_API_KEY)", file=_sys.stderr, flush=True)
        return {"error": "OpenAI client not configured (set OPENAI_API_KEY)."}
    judge_model = model or os.getenv("OPENAI_JUDGE_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    judge_model_str = str(judge_model or "")
    judge_model_lower = judge_model_str.lower()
    use_responses_api = "gpt-4o" in judge_model_lower

    # Payload contains only rubric-provided instructions and evaluation context; no inline Python instructions
    payload = {
        "answer_to_evaluate": answer_to_evaluate,
        "inventory": inventory or {},
    }

    rubric_text = str(rubric_markdown or "").strip()
    # Track-aware but concise system prompt
    track_l = str(track or "").strip().lower()
    track_display = {
        "design": "DESIGN",
        "analysis": "ANALYSIS",
        "debugging": "DEBUGGING"
    }.get(track_l, "design/analysis/debugging")

    sys_prompt = (
        f"You are an impartial grading assistant for analog/mixed-signal circuit {track_display}. "
        "You ONLY output JSON and never prose. Score the answer using the rubric and inventory. "
        "The `overall` field must be a computed numeric value (0-1), not a formula."
    )

    # Single user message: rubric markdown + serialized context
    instr = rubric_text
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": instr + "\n\nCONTEXT:\n" + json.dumps(payload, indent=2)},
    ]

    judge_temp = float(os.getenv("OPENAI_JUDGE_TEMPERATURE", 0.0))
    judge_max = int(os.getenv("OPENAI_JUDGE_MAX_TOKENS", 400))
    # Flexible param handling: adapt for different API surfaces
    if use_responses_api:
        params: Dict[str, Any] = {
            "model": judge_model,
            "instructions": sys_prompt,
            "input": instr + "\n\nCONTEXT:\n" + json.dumps(payload, indent=2),
            "max_output_tokens": judge_max,
        }
        if judge_temp:
            params["temperature"] = judge_temp
    else:
        params = {
            "model": judge_model,
            "messages": messages,
            "temperature": judge_temp,
            "max_tokens": judge_max,
        }
        # Some models require max_completion_tokens instead of max_tokens
        if "gpt-5" in judge_model_lower:
            params.pop("max_tokens", None)
            params.pop("temperature", None)

    def _parse_retry_after(msg: str) -> float:
        """
        Parse a retry-after duration from a text message, accepting values in seconds or milliseconds.
        
        Returns:
            float: The parsed delay in seconds, or 0.0 if no parseable duration is found.
        """
        m = re.search(r"try again in\s*([0-9]+\.?[0-9]*)\s*(ms|s)", msg, flags=re.I)
        if m:
            try:
                val = float(m.group(1))
                return val / 1000.0 if m.group(2).lower() == "ms" else val
            except Exception:
                pass
        return 0.0
    
    def _extract_text(resp_obj: Any, source: str) -> str:
        """
        Extract textual content from an OpenAI API response object produced by either the Responses API or the Chat Completions API.
        
        Parameters:
            resp_obj (Any): The response object returned by the OpenAI client (Responses API output or chat/completions result).
            source (str): Hint for which API surface to parse; use "responses" to force Responses-API parsing, otherwise chat parsing is attempted.
        
        Returns:
            str: The extracted text content trimmed of surrounding whitespace, or an empty string if no usable text is found.
        """
        if resp_obj is None:
            return ""
        if use_responses_api or source == "responses":
            txt = (getattr(resp_obj, "output_text", None) or "").strip()
            if txt:
                return txt
            dump = {}
            try:
                dump = resp_obj.model_dump()  # type: ignore[attr-defined]
            except Exception:
                pass
            out_list = (dump.get("output") or dump.get("outputs") or []) if isinstance(dump, dict) else []
            if isinstance(out_list, list):
                for out in out_list:
                    cont = (out or {}).get("content") or []
                    if isinstance(cont, list):
                        for part in cont:
                            t = part.get("text") or part.get("content")
                            if isinstance(t, str) and t.strip():
                                return t.strip()
            return ""
        # chat completions response
        if hasattr(resp_obj, "choices") and resp_obj.choices:
            return (getattr(resp_obj.choices[0].message, "content", None) or "").strip()
        return ""

    def _log_empty_response(resp_obj: Any, source: str) -> None:
        """
        Log a short diagnostic snippet for an empty or invalid API response.
        
        Attempts to obtain a serializable representation of resp_obj (using model_dump() if available, falling back to repr), truncates the resulting payload to 600 characters, and writes a single-line diagnostic message to stderr prefixed with "[JUDGE] empty {source} response:".
        
        Parameters:
            resp_obj (Any): The response object returned by the OpenAI client (or similar). May be any type; the function will try to serialize it safely.
            source (str): A short label describing the API surface or origin of the response (for example "responses" or "chat"), included in the logged message.
        """
        try:
            dump = resp_obj.model_dump() if hasattr(resp_obj, "model_dump") else {}
        except Exception:
            dump = {}
        try:
            payload = json.dumps(dump) if dump else repr(resp_obj)
        except Exception:
            payload = repr(resp_obj)
        snippet = payload[:600]
        print(f"[JUDGE] empty {source} response: {snippet}", file=_sys.stderr, flush=True)

    def _detect_and_set_tpm(emsg: str) -> None:
        """
        Detects a transactions-per-minute (TPM) limit from an OpenAI rate-limit error message and applies it to the process.
        
        If a "Limit <number>" pattern is found in `emsg` and no TPM has been detected yet, sets the module-level `_DETECTED_TPM` to 90% of the reported value, sets the `OPENAI_JUDGE_TPM` environment variable to that value, and clears the "openai_judge" limiter so it will be recreated with the new TPM. If parsing or application fails, a diagnostic message is printed to stderr.
        
        Parameters:
            emsg (str): Error message text to search for a "Limit <number>" pattern.
        """
        global _DETECTED_TPM
        with _DETECTED_TPM_LOCK:
            if _DETECTED_TPM is not None:
                return
            m = re.search(r"Limit\s+([0-9]+)", emsg, flags=re.I)
            if m:
                try:
                    tpm_value = int(float(m.group(1)) * 0.9)
                    _DETECTED_TPM = tpm_value
                    os.environ["OPENAI_JUDGE_TPM"] = str(tpm_value)
                    print(f"[JUDGE] Auto-detected TPM limit: {m.group(1)}, setting to {tpm_value} (90% safety margin)", file=_sys.stderr, flush=True)
                    # Clear limiter to force recreation with new TPM
                    with _LIM_LOCK:
                        _LIMITERS.pop("openai_judge", None)
                except Exception as e:
                    print(f"[JUDGE] Failed to parse TPM limit: {e}", file=_sys.stderr, flush=True)

    max_attempts = int(os.getenv("OPENAI_JUDGE_MAX_RETRIES", 6))
    base_delay = float(os.getenv("OPENAI_JUDGE_BACKOFF_BASE", 1.0))
    attempt = 0
    resp = None
    # Prepare rate limiting config (computed once, used per attempt)
    est_tokens = int((len(sys_prompt) + len(instr) + len(json.dumps(payload, indent=2))) / float(os.getenv("OPENAI_JUDGE_TOKEN_DIVISOR", 3.5))) + int(judge_max)
    rpm = float(os.getenv("OPENAI_JUDGE_RPM", os.getenv("OPENAI_RPM", 0)) or 0)
    last_err = None
    total_timer = perf_counter() if profiling.is_enabled() else None

    def _log_total_duration() -> None:
        if total_timer is not None:
            profiling.log("judge", "score", (perf_counter() - total_timer) * 1000, context=f"model={judge_model}")

    with _sem():
        while attempt < max_attempts and resp is None:
            attempt += 1
            # Re-read TPM in case it was auto-detected during error handling
            tpm = float(os.getenv("OPENAI_JUDGE_TPM", os.getenv("OPENAI_TPM", 0)) or 0)
            # Cross-thread rate limiting for judge (checked before each API attempt)
            if rpm > 0 or tpm > 0:
                try:
                    get_limiter("openai_judge", rpm=rpm, tpm=tpm).acquire(
                        token_cost=est_tokens,
                        req_cost=1.0,
                        enable_profiling=profiling.is_enabled(),
                    )
                except Exception as rate_err:
                    print(f"[JUDGE] rate limiter error (attempt {attempt}/{max_attempts}): {rate_err}", file=_sys.stderr, flush=True)
            try:
                # OpenAI client timeout is set in _client(), but add explicit timeout as backup
                api_timeout = float(os.getenv("OPENAI_JUDGE_TIMEOUT", os.getenv("OPENAI_TIMEOUT", "60.0")))
                api_timer = perf_counter() if profiling.is_enabled() else None
                if use_responses_api:
                    resp = client.responses.create(timeout=api_timeout, **params)
                else:
                    resp = client.chat.completions.create(**params, timeout=api_timeout)
                    # Validate response before breaking
                    if resp is None or not hasattr(resp, "choices") or not resp.choices:
                        raise ValueError(f"Invalid response from API: {type(resp).__name__}")
                if api_timer is not None:
                    endpoint = "responses" if use_responses_api else "chat"
                    profiling.log(
                        "judge_api",
                        "call",
                        (perf_counter() - api_timer) * 1000,
                        context=f"endpoint={endpoint} model={judge_model}",
                    )
                break
            except APITimeoutError as e:
                emsg = f"API call timed out after {api_timeout}s"
                last_err = emsg
                print(f"[JUDGE] timeout (attempt {attempt}/{max_attempts}): {emsg}", file=_sys.stderr, flush=True)
                # Retry on timeout unless max attempts reached
                if attempt < max_attempts:
                    delay = base_delay * (2 ** (attempt - 1))
                    delay += _rnd.uniform(0.1, 0.5)
                    print(f"[JUDGE] retrying after timeout; delay {delay:.1f}s", file=_sys.stderr, flush=True)
                    time.sleep(min(delay, 10.0))
                    continue
                break
            except Exception as e:
                # Capture error message more robustly
                emsg = str(getattr(e, "message", ""))
                if not emsg:
                    emsg = str(e)
                if not emsg:
                    emsg = f"{type(e).__name__}: {repr(e)}"
                last_err = emsg
                # Log full exception for debugging on first attempt
                if attempt == 1:
                    print(f"[JUDGE] Exception details: {traceback.format_exc()}", file=_sys.stderr, flush=True)
                txt = emsg.lower()
                adapted = False
                # Adapt for models that need max_completion_tokens instead of max_tokens
                if not use_responses_api:
                    if ("max_tokens" in txt or "max_completion_tokens" in txt) and ("does not support" in txt or "unsupported" in txt or "invalid" in txt):
                        if "max_tokens" in params:
                            params.pop("max_tokens", None)
                            params["max_completion_tokens"] = judge_max
                            adapted = True
                else:
                    if ("max_output_tokens" in txt or "max_tokens" in txt) and ("does not support" in txt or "unsupported" in txt or "invalid" in txt):
                        params["max_output_tokens"] = judge_max
                        adapted = True
                if "temperature" in txt and ("unsupported" in txt or "does not support" in txt or "only the default" in txt):
                    params.pop("temperature", None)
                    adapted = True
                if adapted:
                    print(f"[JUDGE] adapting params and retrying (attempt {attempt}/{max_attempts}): {emsg}", file=_sys.stderr, flush=True)
                    continue
                is_rate = ("rate limit" in txt) or ("429" in txt) or ("tpm" in txt) or ("rpm" in txt)
                is_overload = ("service unavailable" in txt) or ("overloaded" in txt) or ("temporarily" in txt) or ("timeout" in txt)
                if is_rate or is_overload:
                    if is_rate and "tpm" in txt:
                        _detect_and_set_tpm(emsg)
                    parsed = _parse_retry_after(emsg)
                    delay = parsed if parsed > 0 else (base_delay * (2 ** (attempt - 1)))
                    delay += _rnd.uniform(0.1, 0.5)
                    print(f"[JUDGE] rate-limited/overloaded; retry {attempt}/{max_attempts} after {delay:.1f}s: {emsg}", file=_sys.stderr, flush=True)
                    time.sleep(min(delay, 20.0))
                    continue
                # Unhandled error: stop
                print(f"[JUDGE] error (no retry): {emsg}", file=_sys.stderr, flush=True)
                break
    if resp is None:
        # All retries failed - return error without accessing resp
        dbg = {
            "system": sys_prompt,
            "instructions": instr,
            "payload": payload,
            "judge_model": judge_model,
        }
        if last_err:
            print(f"[JUDGE] final failure after {attempt} attempts: {last_err}", file=_sys.stderr, flush=True)
        else:
            # This should rarely happen with improved error handling, but provide debug info if it does
            print(f"[JUDGE] final failure after {attempt} attempts: no response (no exception captured)", file=_sys.stderr, flush=True)
            print(f"[JUDGE] debug: client={client is not None}, judge_model={judge_model}, params keys={list(params.keys())}", file=_sys.stderr, flush=True)
        _log_total_duration()
        return {"error": last_err or "Judge failed without response.", "debug": dbg}
    txt = _extract_text(resp, "responses" if use_responses_api else "chat")
    if not txt:
        _log_empty_response(resp, "responses" if use_responses_api else "chat")
        if not use_responses_api:
            # Fallback to Responses API for models that do not return content here
            try:
                api_timeout = float(os.getenv("OPENAI_JUDGE_TIMEOUT", os.getenv("OPENAI_TIMEOUT", "60.0")))
                api_timer2 = perf_counter() if profiling.is_enabled() else None
                r2 = client.responses.create(
                    model=judge_model,
                    instructions=sys_prompt,
                    input=(instr + "\n\nCONTEXT:\n" + json.dumps(payload)),
                    max_output_tokens=judge_max,
                    timeout=api_timeout,
                )
                if api_timer2 is not None:
                    profiling.log(
                        "judge_api",
                        "call",
                        (perf_counter() - api_timer2) * 1000,
                        context=f"endpoint=responses-fallback model={judge_model}",
                    )
                txt = _extract_text(r2, "responses")
                if not txt:
                    _log_empty_response(r2, "responses-fallback")
            except Exception as fallback_err:
                print(f"[JUDGE] responses fallback failed: {fallback_err}", file=_sys.stderr, flush=True)
                txt = "{}"
    
    # Strip markdown code fences if present (common with Responses API)
    txt = txt.strip()
    if txt.startswith("```json"):
        txt = txt[7:]  # Remove ```json
    elif txt.startswith("```"):
        txt = txt[3:]  # Remove ```
    if txt.endswith("```"):
        txt = txt[:-3]  # Remove closing ```
    txt = txt.strip()
    
    try:
        data = json.loads(txt)
        # basic shape check
        if not isinstance(data, dict) or "scores" not in data:
            print("[JUDGE] unexpected response shape; no 'scores' in judge output", file=_sys.stderr, flush=True)
            return {"error": "Judge returned unexpected format.", "raw": txt}
        # Attach debug info to help diagnose judging disagreements
        try:
            data["debug"] = {
                "system": sys_prompt,
                "instructions": instr,
                "payload": payload,
                "judge_model": judge_model,
            }
        except Exception:
            pass
        return data
    except Exception as parse_err:
        # Return a structured error with debug payload for renderer
        print(f"[JUDGE] JSON parse error: {parse_err}", file=_sys.stderr, flush=True)
        print(f"[JUDGE] Raw text (first 500 chars): {txt[:500]}", file=_sys.stderr, flush=True)
        dbg = {
            "system": sys_prompt,
            "instructions": instr,
            "payload": payload,
            "judge_model": judge_model,
        }
        if last_err:
            print(f"[JUDGE] final failure after {attempt} attempts: {last_err}", file=_sys.stderr, flush=True)
        else:
            print(f"[JUDGE] final failure after {attempt} attempts: no response", file=_sys.stderr, flush=True)
        out = {"error": last_err or "Judge failed without response.", "debug": dbg}
        _log_total_duration()
        return out
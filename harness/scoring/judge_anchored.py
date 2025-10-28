from __future__ import annotations
import json
import os
from typing import Any, Dict, Optional
import time
import random as _rnd
import re
from ..utils.rate_limiter import get_limiter
import threading
import os as _os
import sys as _sys

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


def _client() -> Optional[Any]:
    if OpenAI is None:
        return None
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


_SEM: threading.Semaphore | None = None


def _sem() -> threading.Semaphore:
    global _SEM
    if _SEM is None:
        try:
            lim = int(_os.getenv("OPENAI_JUDGE_CONCURRENCY", "0") or "0")
        except Exception:
            lim = 0
        if lim and lim > 0:
            _SEM = threading.Semaphore(lim)
        else:
            # Default to modest concurrency if unset
            _SEM = threading.Semaphore(8)
    return _SEM


def judge_answer(
    answer: str,
    rubric_markdown: str,
    refs: Dict[str, Any],
    inventory: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    client = _client()
    if client is None:
        print("[JUDGE] OpenAI client not configured (set OPENAI_API_KEY)", file=_sys.stderr, flush=True)
        return {"error": "OpenAI client not configured (set OPENAI_API_KEY)."}
    judge_model = model or os.getenv("OPENAI_JUDGE_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    # Payload contains only rubric-provided instructions and evaluation context; no inline Python instructions
    payload = {
        "refs": refs,
        "answer": answer,
        "inventory": inventory or {},
    }

    rubric_text = str(rubric_markdown or "").strip()
    # Track-aware but concise system prompt
    track = (refs or {}).get("track")
    track_l = str(track or "").strip().lower()
    if track_l == "design":
        sys_prompt = (
            "You are an impartial grading assistant for analog/mixed-signal circuit DESIGN. "
            "You ONLY output JSON and never prose. Score the answer per rubric using the provided refs and inventory."
        )
    elif track_l == "analysis":
        sys_prompt = (
            "You are an impartial grading assistant for analog/mixed-signal circuit ANALYSIS. "
            "You ONLY output JSON and never prose. Score the answer per rubric using the provided refs and inventory."
        )
    elif track_l == "debugging":
        sys_prompt = (
            "You are an impartial grading assistant for analog/mixed-signal circuit DEBUGGING. "
            "You ONLY output JSON and never prose. Score the answer per rubric using the provided refs and inventory."
        )
    else:
        sys_prompt = (
            "You are an impartial grading assistant for analog/mixed-signal design/analysis/debugging. "
            "You ONLY output JSON and never prose. Score the answer per rubric using the provided refs and inventory."
        )

    # Single user message: rubric markdown + serialized context
    instr = rubric_text
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": instr + "\n\nCONTEXT:\n" + json.dumps(payload)},
    ]

    judge_temp = float(os.getenv("OPENAI_JUDGE_TEMPERATURE", 0.0))
    judge_max = int(os.getenv("OPENAI_JUDGE_MAX_TOKENS", 400))
    # Flexible param handling: adapt for max_completion_tokens and temperature when unsupported
    params: Dict[str, Any] = {
        "model": judge_model,
        "messages": messages,
        "temperature": judge_temp,
        "max_tokens": judge_max,
    }
    if "gpt-5" in str(judge_model or "").lower():
        params.pop("max_tokens", None)
        params.pop("temperature", None)

    def _parse_retry_after(msg: str) -> float:
        m = re.search(r"try again in\s*([0-9]+\.?[0-9]*)s", msg, flags=re.I)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                return 0.0
        return 0.0

    max_attempts = int(os.getenv("OPENAI_JUDGE_MAX_RETRIES", 6))
    base_delay = float(os.getenv("OPENAI_JUDGE_BACKOFF_BASE", 1.0))
    attempt = 0
    resp = None
    # Cross-thread rate limiting for judge
    try:
        # Estimate tokens: rubric + serialized payload text + completion budget
        est_tokens = int((len(instr) + len(json.dumps(payload))) / float(os.getenv("OPENAI_JUDGE_TOKEN_DIVISOR", 4))) + int(judge_max)
        rpm = float(os.getenv("OPENAI_JUDGE_RPM", os.getenv("OPENAI_RPM", 0)) or 0)
        tpm = float(os.getenv("OPENAI_JUDGE_TPM", os.getenv("OPENAI_TPM", 0)) or 0)
        if rpm > 0 or tpm > 0:
            get_limiter("openai_judge", rpm=rpm, tpm=tpm).acquire(token_cost=est_tokens, req_cost=1.0)
    except Exception:
        pass
    last_err = None
    with _sem():
        while attempt < max_attempts and resp is None:
            attempt += 1
            try:
                resp = client.chat.completions.create(**params)
                break
            except Exception as e:
                emsg = str(getattr(e, "message", e))
                last_err = emsg or str(e)
                txt = (emsg or str(e)).lower()
                adapted = False
                if "max_tokens" in txt and "max_completion_tokens" in txt:
                    params.pop("max_tokens", None)
                    params["max_completion_tokens"] = judge_max
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
                    parsed = _parse_retry_after(emsg)
                    delay = parsed if parsed > 0 else (base_delay * (2 ** (attempt - 1)))
                    delay += _rnd.uniform(0.1, 0.5)
                    print(f"[JUDGE] rate-limited/overloaded; retry {attempt}/{max_attempts} after {delay:.1f}s: {emsg}", file=_sys.stderr, flush=True)
                    time.sleep(min(delay, 20.0))
                    continue
                # Unhandled error: stop
                print(f"[JUDGE] error (no retry): {emsg}", file=_sys.stderr, flush=True)
                break
    txt = (getattr(resp.choices[0].message, "content", None) or "").strip()
    if not txt:
        # Fallback to Responses API for models that do not return content here
        try:
            r2 = client.responses.create(
                model=judge_model,
                instructions=sys_prompt,
                input=(instr + "\n\nCONTEXT:\n" + json.dumps(payload)),
                max_output_tokens=judge_max,
            )
            txt = (getattr(r2, "output_text", None) or "").strip()
            if not txt:
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
                                    txt = t.strip()
                                    break
                            if txt:
                                break
        except Exception:
            txt = "{}"
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
    except Exception:
        # Return a structured error with debug payload for renderer
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
        return out

from __future__ import annotations
import json
import os
from typing import Any, Dict, Optional

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


JUDGE_SYS = (
    "You are an impartial grading assistant for analog/mixed-signal design. "
    "You ONLY output JSON. Your job is to score the answer per rubric, strictly anchored to the provided knowledge, refs, and inventory."
)


def _client() -> Optional[Any]:
    if OpenAI is None:
        return None
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def judge_answer(
    answer: str,
    rubric_json: Dict[str, Any],
    knowledge_snippets: str,
    refs: Dict[str, Any],
    model: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    client = _client()
    if client is None:
        return None
    judge_model = model or os.getenv("OPENAI_JUDGE_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    payload = {
        "rubric": rubric_json,
        "knowledge": knowledge_snippets,
        "refs": refs,
        "answer": answer,
    }
    instr = (
        "Score the answer per-criterion with values in [0,1]."
        " Required output format (JSON only):\n"
        "{\n  \"scores\": { \"<criterion_id>\": <float 0..1>, ... },\n  \"overall\": <float 0..1>\n}\n"
        "Do not include any other keys or text."
    )
    messages = [
        {"role": "system", "content": JUDGE_SYS},
        {"role": "user", "content": instr + "\n\nCONTEXT:\n" + json.dumps(payload)},
    ]
    judge_temp = float(os.getenv("OPENAI_JUDGE_TEMPERATURE", 0.0))
    judge_max = int(os.getenv("OPENAI_JUDGE_MAX_TOKENS", 400))
    # Flexible param handling like adapter: adapt for max_completion_tokens and temperature.
    params: Dict[str, Any] = {
        "model": judge_model,
        "messages": messages,
        "temperature": judge_temp,
        "max_tokens": judge_max,
    }
    if "gpt-5" in str(judge_model or "").lower():
        params.pop("max_tokens", None)
        params.pop("temperature", None)
    for _ in range(3):
        try:
            resp = client.chat.completions.create(**params)
            break
        except Exception as e:
            emsg = str(getattr(e, "message", e))
            txt = (emsg or str(e)).lower()
            adapted = False
            if "max_tokens" in txt and "max_completion_tokens" in txt:
                params.pop("max_tokens", None)
                params["max_completion_tokens"] = judge_max
                adapted = True
            if "temperature" in txt and ("unsupported" in txt or "does not support" in txt or "only the default" in txt):
                params.pop("temperature", None)
                adapted = True
            if not adapted:
                raise
    txt = (getattr(resp.choices[0].message, "content", None) or "").strip()
    if not txt:
        # Fallback to Responses API for models that do not return content here
        try:
            r2 = client.responses.create(
                model=judge_model,
                instructions=JUDGE_SYS,
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
            return None
        return data
    except Exception:
        return None

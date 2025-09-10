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
    resp = client.chat.completions.create(
        model=judge_model,
        temperature=float(os.getenv("OPENAI_JUDGE_TEMPERATURE", 0.0)),
        max_tokens=int(os.getenv("OPENAI_JUDGE_MAX_TOKENS", 400)),
        messages=messages,
    )
    txt = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(txt)
        # basic shape check
        if not isinstance(data, dict) or "scores" not in data:
            return None
        return data
    except Exception:
        return None

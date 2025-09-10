from __future__ import annotations
import re
from typing import Iterable, List, Tuple


def contains_any(text: str, patterns: Iterable[str]) -> bool:
    t = text.lower()
    for p in patterns:
        if re.search(re.escape(p.lower()), t):
            return True
    return False


def count_any(text: str, patterns: Iterable[str]) -> int:
    t = text.lower()
    cnt = 0
    for p in patterns:
        if re.search(re.escape(p.lower()), t):
            cnt += 1
    return cnt


code_id_re = re.compile(r"`([A-Za-z0-9_./-]+)`")
token_id_re = re.compile(r"\b([A-Za-z]{1,4}[0-9]{1,3}|CMFB|CL|Cc|VDD|VSS|GND|vinp|vinn|vout)\b")


def extract_citations(answer: str) -> List[str]:
    ids = []
    ids += code_id_re.findall(answer)
    ids += token_id_re.findall(answer)
    # Keep unique order
    seen = set()
    uniq = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    return uniq


def sectionize_markdown(answer: str) -> List[Tuple[str, str]]:
    # Very lightweight section splitter by leading markdown headers
    parts: List[Tuple[str, str]] = []
    current = None
    buf: List[str] = []
    for line in answer.splitlines():
        if line.strip().startswith('#'):
            if current is not None:
                parts.append((current, "\n".join(buf).strip()))
            current = re.sub(r"^#+\s*", "", line).strip().lower()
            buf = []
        else:
            buf.append(line)
    if current is not None:
        parts.append((current, "\n".join(buf).strip()))
    return parts


from __future__ import annotations
import re
from typing import Dict, Optional
from pathlib import Path

_VAR_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")
_PATH_RE = re.compile(r"\{path:([^}]+)\}")

def render_template(text: str, vars: Dict[str, str], base_dir: Optional[str | Path] = None) -> str:
    """Render a lightweight bracket-template by:
    1) Resolving include directives of the form {path:relative/or/absolute.md} relative to base_dir
    2) Replacing {var} placeholders with provided string values.
    Missing variables are left as-is to surface gaps during validation.
    Includes are resolved recursively.
    """
    base = Path(base_dir) if base_dir is not None else None

    def _resolve_includes(s: str, depth: int = 0) -> str:
        if depth > 8:
            return s  # guard against cycles
        out = s
        for m in list(_PATH_RE.finditer(s)):
            raw = m.group(0)
            rel = m.group(1).strip()
            try:
                p = Path(rel)
                if not p.is_absolute() and base is not None:
                    p = (base / p).resolve()
                content = p.read_text(encoding="utf-8")
                content = _resolve_includes(content, depth + 1)
                out = out.replace(raw, content)
            except Exception:
                # leave as-is if cannot read
                continue
        return out

    # 1) includes
    with_includes = _resolve_includes(text)
    # 2) variables
    def _sub(m: re.Match[str]) -> str:
        key = m.group(1)
        return str(vars.get(key, m.group(0)))
    return _VAR_RE.sub(_sub, with_includes)

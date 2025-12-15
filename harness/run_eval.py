from __future__ import annotations
import argparse
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from time import perf_counter
import hashlib
import math
import random
import yaml

from rich import print
from rich.progress import Progress, BarColumn, TimeElapsedColumn, TimeRemainingColumn, MofNCompleteColumn
from rich.table import Table
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import threading

# Allow running as script or module
if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from harness.types import Inventory, Question, EvalItem  # type: ignore
    from harness.scoring.groundedness import groundedness  # type: ignore
    from harness.reporting.render import generate_report, generate_outputs_index  # type: ignore
    from harness.utils.template import render_template  # type: ignore
    from harness.utils import profiling  # type: ignore
else:
    from .types import Inventory, Question, EvalItem
    from .scoring.groundedness import groundedness
    from .reporting.render import generate_report, generate_outputs_index
    from .utils.template import render_template
    from .utils import profiling


import importlib
ADAPTERS: Dict[str, Any] = {}


def get_adapter(name: str, **kwargs):
    global ADAPTERS
    if not ADAPTERS:
        # Attempt absolute import first (works when run as script after sys.path tweak)
        try:
            mod = importlib.import_module("harness.adapters.dummy")
            ADAPTERS["dummy"] = getattr(mod, "build")
        except Exception:
            # Fallback to relative import when run as module
            from .adapters.dummy import build as build_dummy
            ADAPTERS["dummy"] = build_dummy
        # Optional OpenAI adapter
        try:
            mod2 = importlib.import_module("harness.adapters.openai")
            ADAPTERS["openai"] = getattr(mod2, "build")
        except Exception:
            try:
                from .adapters.openai import build as build_openai
                ADAPTERS["openai"] = build_openai
            except Exception:
                pass
        # Optional Anthropic adapter
        try:
            mod3 = importlib.import_module("harness.adapters.anthropic")
            ADAPTERS["anthropic"] = getattr(mod3, "build")
        except Exception:
            try:
                from .adapters.anthropic import build as build_anthropic
                ADAPTERS["anthropic"] = build_anthropic
            except Exception:
                pass
        # Optional OpenRouter adapter
        try:
            mod4 = importlib.import_module("harness.adapters.openrouter")
            ADAPTERS["openrouter"] = getattr(mod4, "build")
        except Exception:
            try:
                from .adapters.openrouter import build as build_openrouter
                ADAPTERS["openrouter"] = build_openrouter
            except Exception:
                pass
        # Optional Google adapter
        try:
            mod5 = importlib.import_module("harness.adapters.google")
            ADAPTERS["google"] = getattr(mod5, "build")
        except Exception:
            try:
                from .adapters.google import build as build_google
                ADAPTERS["google"] = build_google
            except Exception:
                pass
    if name not in ADAPTERS:
        raise ValueError(f"Unknown adapter: {name}")
    build_fn = ADAPTERS[name]
    try:
        return build_fn(**kwargs)
    except TypeError:
        # Back-compat for builders without kwargs signature
        return build_fn()


def parse_model_spec(spec: str) -> tuple[str, Dict[str, Any]]:
    """
    Parse a model spec like "openai", "openai:gpt-4o-mini", or "openai:gpt-5-nano:low" into (adapter, kwargs).
    Supports optional effort level as third component: adapter:model:effort
    For unknown adapters, everything after ':' is ignored.
    """
    if ":" in spec:
        parts = spec.split(":")
        name = parts[0].strip()
        rest = parts[1].strip() if len(parts) > 1 else ""
        effort = parts[2].strip() if len(parts) > 2 else None
        
        kwargs: Dict[str, Any] = {}
        
        # For OpenAI, map to underlying model name and optional reasoning effort
        if name == "openai" and rest:
            kwargs["model"] = rest
            if effort:
                kwargs["reasoning_effort"] = effort
        # For Anthropic, map to underlying model name
        elif name == "anthropic" and rest:
            kwargs["model"] = rest
        # For OpenRouter, pass model name through
        elif name == "openrouter" and rest:
            kwargs["model"] = rest
        # For Google, map to underlying model name and optional thinking budget (effort level)
        elif name == "google" and rest:
            kwargs["model"] = rest
            if effort:
                kwargs["thinking_budget"] = effort
        # Future adapters can parse additional kv-pairs here
        else:
            if rest:
                kwargs["model"] = rest
        
        return name, kwargs
    return spec.strip(), {}


def normalize_judge_model(spec: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Normalize judge model specs so we can reuse adapter-style strings
    (e.g., openai:gpt-4o-mini or openai:gpt-5-nano:low) while still passing raw model IDs to judge calls.
    Also handles specs without adapter prefix (e.g., gpt-5-nano:minimal).
    Returns (model_name, effort_level) where effort_level may be None.
    """
    if spec is None:
        return None, None
    cleaned = str(spec).strip()
    if not cleaned:
        return None, None
    if ":" in cleaned:
        parts = cleaned.split(":")
        prefix = parts[0].strip()
        rest = parts[1].strip() if len(parts) > 1 else ""
        effort = parts[2].strip() if len(parts) > 2 else None
        
        # If prefix is a known adapter, extract model name and effort
        if prefix.lower() in {"openai", "anthropic", "openrouter", "google"}:
            return rest or None, effort
        # If prefix is not a known adapter, assume it's a model name with optional effort
        # (e.g., "gpt-5-nano:minimal" -> model="gpt-5-nano", effort="minimal")
        if len(parts) == 2:
            # Two parts: model:effort
            return prefix, rest
        elif len(parts) == 3:
            # Three parts: adapter:model:effort (but adapter not recognized)
            # Treat as model:effort:something (unlikely but handle gracefully)
            return prefix, rest
        else:
            # More than 3 parts - return first part as model, second as effort
            return prefix, rest
    return cleaned, None


def load_questions(item_dir: Path) -> List[Question]:
    """Load questions; support 'auto' modality expansion from meta.json.
    If a question has modality in {"auto","*","all"} or is missing, expand
    into one question per available modality with inferred artifact paths.
    """
    q_path = item_dir / "questions.yaml"
    if not q_path.exists():
        raise FileNotFoundError(f"questions.yaml not found in {item_dir}")

    meta_path = item_dir / "meta.json"
    # Map modality -> artifact filename
    artifact_by_modality = {
        "spice_netlist": "netlist.sp",
        "veriloga": "veriloga.va",
        # New representations
        "cascode": "netlist.cas",  # ADL (Alt circuit description language)
        "casIR": "netlist.cir",    # Intermediate representation
    }
    # Back-compat: map old modality names
    canonical_modality = {
        "casir": "casIR",
    }

    template_rel_hint: Optional[str] = None
    template_abs_hint: Optional[Path] = None

    def _structure_template_abs() -> Optional[Path]:
        try:
            split_root = item_dir.parents[2]
            rel = item_dir.relative_to(split_root)
            parts = rel.parts
            if len(parts) >= 2:
                tail = Path(*parts[1:])
                return split_root / "templates" / tail
        except Exception:
            return None
        return None

    def _structure_template_rel(abs_path: Path) -> str:
        rel = os.path.relpath(abs_path, item_dir)
        return rel.replace("\\", "/")

    meta: Dict[str, Any] = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
        except Exception:
            meta = {}

    mlist = meta.get("modalities") or []
    tpl_rel_val = meta.get("template_path") or meta.get("template")
    if isinstance(tpl_rel_val, str) and tpl_rel_val.strip():
        template_rel_hint = Path(tpl_rel_val.strip()).as_posix()
        try:
            template_abs_hint = (item_dir / tpl_rel_val).resolve()
        except Exception:
            template_abs_hint = None

    if template_abs_hint is None:
        template_abs_hint = _structure_template_abs()
    if template_rel_hint is None and template_abs_hint is not None:
        template_rel_hint = _structure_template_rel(template_abs_hint)

    available_modalities: List[str] = []
    seen_modalities: set[str] = set()

    def _register_modality(candidate: Any) -> None:
        mod = canonical_modality.get(str(candidate), str(candidate))
        if mod not in artifact_by_modality:
            return
        if mod in seen_modalities:
            return
        ap_name = artifact_by_modality[mod]
        exists_local = (item_dir / ap_name).exists()
        exists_tpl = bool(template_abs_hint and (template_abs_hint / ap_name).exists())
        if exists_local or exists_tpl:
            seen_modalities.add(mod)
            available_modalities.append(mod)

    if isinstance(mlist, list):
        for m in mlist:
            _register_modality(m)

    for m in artifact_by_modality.keys():
        _register_modality(m)

    if not available_modalities:
        default_mod = "spice_netlist"
        seen_modalities.add(default_mod)
        available_modalities.append(default_mod)

    default_artifact_root = template_rel_hint

    def _default_artifact_for(filename: str) -> str:
        if default_artifact_root:
            return (Path(default_artifact_root) / filename).as_posix()
        return Path(filename).as_posix()

    prompts_dir = item_dir.parent / "prompts"

    def _extract_sections_from_prompt(prompt_name: str) -> List[str]:
        # Resolve prompt_name relative to item_dir (e.g., ../prompts/design_ota.txt)
        ppath = (item_dir / prompt_name).resolve()
        try:
            lines = ppath.read_text(encoding='utf-8').splitlines()
        except Exception:
            # If file not found, return empty list (sections extraction is optional)
            return []
        sections: List[str] = []
        capture = False
        for raw in lines:
            line = raw.strip()
            if not line:
                if capture:
                    break
                continue
            if not capture:
                if line.lower().startswith("required sections"):
                    capture = True
                continue
            if line.startswith("-"):
                section = line[1:].strip().strip(":")
                if section:
                    sections.append(section)
            else:
                break
        return sections

    def _apply_defaults(qdict: Dict[str, Any]) -> Dict[str, Any]:
        if not qdict.get("prompt_template") and not qdict.get("prompt_path"):
            raise SystemExit(
                f"Question {qdict.get('id')} in {item_dir} must specify prompt_template or prompt_path."
            )
        # Supply required sections when omitted by reading prompt header
        if not qdict.get("require_sections"):
            prompt_name = qdict.get("prompt_template") or qdict.get("prompt_path", "")
            if prompt_name:
                sections = _extract_sections_from_prompt(str(prompt_name))
                if sections:
                    qdict["require_sections"] = sections
        if not qdict.get("require_sections"):
            qdict["require_sections"] = ["Answer"]
        
        # Skip judge defaults for verification-only questions
        is_verification_only = (
            qdict.get("verification", {}).get("enabled") and
            not qdict.get("judge_prompt") and
            not qdict.get("judge_id")
        )
        
        # Judge prompt defaults: map prompt_template stem to ../judge_prompts/<stem>.md
        if not qdict.get("judge_prompt") and not is_verification_only:
            try:
                stem = Path(str(qdict["prompt_template"]).strip()).stem
            except Exception:
                stem = "rubric"
            qdict["judge_prompt"] = (Path("../judge_prompts") / f"{stem}.md").as_posix()
        if not qdict.get("judge_id") and not is_verification_only:
            try:
                qdict["judge_id"] = Path(qdict["judge_prompt"]).stem if qdict.get("judge_prompt") else None
            except Exception:
                qdict["judge_id"] = str(qdict.get("id") or "judge")
        # Default answer format to markdown for legacy items
        if not qdict.get("answer_format"):
            qdict["answer_format"] = "markdown"
        return qdict

    raw_questions: List[Dict[str, Any]] = []
    try:
        data = yaml.safe_load(q_path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise SystemExit(f"Failed to load {q_path}: {exc}")
    if isinstance(data, dict):
        entries = data.get("questions") if "questions" in data else [data]
    elif isinstance(data, list):
        entries = data
    else:
        raise SystemExit(f"questions.yaml must contain a list or mapping of questions: {q_path}")
    for entry in entries:
        if isinstance(entry, dict):
            raw_questions.append(entry)

    out: List[Question] = []
    for raw in raw_questions:
        if not isinstance(raw, dict):
            continue
        # Normalize modality and track
        mod = raw.get("modality")
        # Also expand if modality is the umbrella 'design' (back-compat for design family)
        needs_expand = mod in (None, "", "auto", "*", "all", "design")
        base_id = str(raw.get("id", item_dir.name))
        if needs_expand:
            for m in available_modalities:
                ap = artifact_by_modality.get(m)
                if not ap:
                    continue
                qdict = dict(raw)
                qdict["id"] = f"{base_id}_{m}"
                qdict["modality"] = m
                # When expanding modalities, if an explicit artifact_path was provided
                # (e.g., a template-relative path to netlist.sp), rewrite just the
                # filename to the canonical artifact for the specific modality while
                # preserving the directory. This ensures casIR/cascode expansions use
                # netlist.cir/netlist.cas respectively rather than always netlist.sp.
                orig_ap = qdict.get("artifact_path")
                if isinstance(orig_ap, str) and orig_ap.strip():
                    try:
                        # Interpret path relative to the item_dir for existence checks
                        rel = (item_dir / orig_ap)
                        if rel.exists() and rel.is_dir():
                            # Treat as a directory base; append canonical filename
                            new_ap = (Path(orig_ap) / ap).as_posix()
                        else:
                            base = Path(orig_ap)
                            parent = base.parent
                            if str(parent) not in ("", "."):
                                new_ap = (parent / ap).as_posix()
                            else:
                                new_ap = _default_artifact_for(ap)
                    except Exception:
                        new_ap = _default_artifact_for(ap)
                    qdict["artifact_path"] = new_ap
                else:
                    # No explicit path provided; use canonical filename for modality
                    qdict["artifact_path"] = _default_artifact_for(ap)
                qdict = _apply_defaults(qdict)
                out.append(Question.model_validate(qdict))
        else:
            # Normalize modality and artifact path if missing
            m = canonical_modality.get(str(mod), str(mod))
            if not raw.get("artifact_path") and m in artifact_by_modality:
                raw["artifact_path"] = _default_artifact_for(artifact_by_modality[m])
            else:
                # If an artifact_path is provided and points to a directory, append
                # the canonical filename for the modality (supports dir-style inputs).
                try:
                    ap_in = raw.get("artifact_path")
                    if isinstance(ap_in, str) and ap_in.strip() and m in artifact_by_modality:
                        rel = (item_dir / ap_in)
                        if rel.exists() and rel.is_dir():
                            raw["artifact_path"] = (Path(ap_in) / artifact_by_modality[m]).as_posix()
                except Exception:
                    pass
            raw["modality"] = m
            raw = _apply_defaults(raw)
            out.append(Question.model_validate(raw))
            # Special-case: For debugging items authored as spice_netlist only,
            # auto-add parallel questions for any additional available modalities
            # discovered from template (e.g., casIR, cascode).
            try:
                if str(raw.get("track", "")).lower() == "debugging" and m == "spice_netlist":
                    for m2 in available_modalities:
                        if m2 == "spice_netlist":
                            continue
                        qdict = dict(raw)
                        qdict["id"] = f"{base_id}_{m2}"
                        qdict["modality"] = m2
                        # Rewrite artifact_path to bugged file if original used bugged SPICE
                        ap_in = str(raw.get("artifact_path", "")).strip()
                        canonical = artifact_by_modality[m2]
                        new_ap = _default_artifact_for(canonical)
                        if ap_in:
                            try:
                                rel = (item_dir / ap_in)
                                if rel.exists() and rel.is_dir():
                                    new_ap = (Path(ap_in) / canonical).as_posix()
                                else:
                                    # If using bugged SPICE artifact, mirror to bugged filename for modality
                                    if ap_in.endswith("netlist_bug.sp"):
                                        if m2 == "casIR":
                                            new_ap = Path("netlist_bug.cir").as_posix()
                                        elif m2 == "cascode":
                                            new_ap = Path("netlist_bug.cas").as_posix()
                                    else:
                                        new_ap = _default_artifact_for(canonical)
                            except Exception:
                                new_ap = _default_artifact_for(canonical)
                        qdict["artifact_path"] = new_ap
                        out.append(Question.model_validate(qdict))
            except Exception:
                # Be permissive if auto-add fails
                pass
    return out


def load_inventory(item_dir: Path) -> Inventory:
    """Load inventory for an item.
    Prefers local inventory.json; if missing, supports template indirection via meta.json:
      { "template_path": "../../templates/ota/ota001" }
    The template path is resolved relative to the item_dir.
    """
    # Prefer template if meta.json declares template_path
    meta_path = item_dir / "meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
            tpath = meta.get("template_path") or meta.get("template") or None
            if isinstance(tpath, str) and tpath.strip():
                tpl_dir = (item_dir / tpath).resolve()
                inv_file = tpl_dir / "inventory.json"
                if inv_file.exists():
                    inv = json.loads(inv_file.read_text(encoding='utf-8'))
                    return Inventory.model_validate(inv)
        except Exception:
            pass
    # Fallback to local inventory.json
    local = item_dir / "inventory.json"
    if local.exists():
        inv = json.loads(local.read_text(encoding='utf-8'))
        return Inventory.model_validate(inv)
    raise FileNotFoundError(f"inventory.json not found for item {item_dir}")


def iter_items(split_dir: Path) -> List[EvalItem]:
    items: List[EvalItem] = []
    # Recursively discover item directories that contain questions, with inventory either local or via template
    for item_dir in sorted([p for p in split_dir.rglob("*") if p.is_dir()]):
        q_path = item_dir / "questions.yaml"
        if not q_path.exists():
            continue
        try:
            inv = load_inventory(item_dir)
        except Exception:
            # Skip directories without a resolvable inventory
            continue
        qs = load_questions(item_dir)
        items.append(EvalItem(item_dir=str(item_dir), inventory=inv, questions=qs))
    return items


# Utility: randomize SPICE netlist
def _unit_scale_to_float(val: str) -> float:
    s = val.strip().lower()
    # Try plain float
    try:
        return float(s)
    except Exception:
        pass
    # SPICE common suffix multipliers
    muls = {
        't': 1e12,
        'g': 1e9,
        'meg': 1e6,
        'k': 1e3,
        'm': 1e-3,
        'u': 1e-6,
        'n': 1e-9,
        'p': 1e-12,
        'f': 1e-15,
    }
    # handle 'meg' specially
    if s.endswith('meg'):
        try:
            return float(s[:-3]) * muls['meg']
        except Exception:
            return 0.0
    # last char as suffix
    if s[-1] in muls:
        try:
            return float(s[:-1]) * muls[s[-1]]
        except Exception:
            return 0.0
    return 0.0


def _float_to_unit(val: float, like: str, sig_digits: Optional[int] = None) -> str:
    # Render with the same unit suffix as 'like' if present. sig_digits limits precision.
    fmt = (lambda x: f"{x:g}") if sig_digits is None else (lambda x: f"{x:.{sig_digits}g}")
    s = like.strip()
    if not s:
        return fmt(val)
    suf = s[-1]
    lower = s.lower()
    if lower.endswith('meg'):
        return f"{fmt(val/1e6)}{s[-3:]}"
    muls = {
        't': 1e12,
        'g': 1e9,
        'k': 1e3,
        'm': 1e-3,
        'u': 1e-6,
        'n': 1e-9,
        'p': 1e-12,
        'f': 1e-15,
    }
    suf_lower = suf.lower()
    if suf_lower in muls:
        scaled = val / muls[suf_lower]
        return f"{fmt(scaled)}{suf}"
    return fmt(val)


def randomize_spice(text: str, seed: int) -> str:
    rnd = random.Random(seed)
    raw_lines = text.splitlines()
    # identify .SUBCKT blocks and keep intact; also treat continuation lines '+' as part of previous statement
    out_lines: List[str] = []
    devices: List[List[str]] = []  # each device may have continuations
    headers: List[str] = []
    footers: List[str] = []  # terminal deck controls like .end, .backanno
    tails: List[str] = []
    in_subckt = False
    subckt_buf: List[str] = []
    subckts: List[List[str]] = []
    current_stmt: List[str] = []
    for ln in raw_lines:
        raw = ln.rstrip('\n')
        s = raw.strip()
        low = s.lower()
        if low.startswith('.subckt'):
            # flush any pending statement before entering subckt
            if current_stmt:
                devices.append(current_stmt)
                current_stmt = []
            in_subckt = True
            subckt_buf = [raw]
            continue
        if in_subckt:
            # Include blank lines inside subcircuit blocks to preserve structure
            subckt_buf.append(raw)
            if low.startswith('.ends'):
                in_subckt = False
                subckts.append(subckt_buf)
            continue
        if not s:
            # keep blank lines in tails for aesthetics later (only for main netlist)
            tails.append(raw)
            continue
        if s[0] in ('*', ';'):
            # flush pending
            if current_stmt:
                devices.append(current_stmt)
                current_stmt = []
            headers.append(raw)
            continue
        if s[0] == '.':
            # flush pending
            if current_stmt:
                devices.append(current_stmt)
                current_stmt = []
            # Classify dot-directives: footer directives go to footers, others to headers
            low_cmd = low.split()[0] if low else ""
            # Footer directives (terminal deck controls)
            footer_commands = {'.end', '.backanno', '.eof'}
            if low_cmd in footer_commands:
                footers.append(raw)
            else:
                # Header directives (.model, .param, .include, .lib, .options, etc.)
                headers.append(raw)
            continue
        if s[0] == '+':
            # continuation of previous
            if current_stmt:
                current_stmt.append(raw)
            else:
                # orphan continuation -> treat as header to be safe
                headers.append(raw)
            continue
        # start of a device/source statement
        if current_stmt:
            devices.append(current_stmt)
        current_stmt = [raw]
    # flush at end
    if current_stmt:
        devices.append(current_stmt)

    # Jitter sizes on MOS and C devices
    def _quantize_like(value: float, reference: float, rel_step: float, min_step: float) -> float:
        if reference <= 0.0:
            return value
        step = max(abs(reference) * rel_step, min_step)
        if step <= 0:
            return value
        quanta = int(round(value / step))
        if quanta < 1:
            quanta = 1
        return quanta * step

    def jitter_device(dev_lines: List[str]) -> List[str]:
        line0 = dev_lines[0]
        s = line0.strip()
        if not s:
            return dev_lines
        # MOS: starts with M/m
        if s[0].lower() == 'm':
            # Scale W by factor and L by small jitter, preserve unit suffix
            parts = s.split()
            # Find W= and L= tokens
            new_parts = []
            w_like = None
            l_like = None
            for tok in parts:
                if tok.upper().startswith('W='):
                    w_like = tok.split('=',1)[1]
                if tok.upper().startswith('L='):
                    l_like = tok.split('=',1)[1]
            # Heuristic: NMOS vs PMOS by model token (5th token typical)
            # Fallback: if contains 'pch' treat as PMOS
            is_p = ' pch ' in f' {s.lower()} '
            base_w = _unit_scale_to_float(w_like) if w_like else 0.0
            base_l = _unit_scale_to_float(l_like) if l_like else 0.0
            w_new: Optional[float] = None
            if base_w > 0.0:
                heavy_tail = rnd.random() < 0.18  # Occasionally sample much larger analog devices
                low = max(base_w * 0.5, 0.2e-6)
                high = 100e-6  # Allow widths up to ~100 µm
                if heavy_tail and high > low:
                    w_candidate = math.exp(rnd.uniform(math.log(low), math.log(high)))
                else:
                    heavy_tail = False
                    w_candidate = base_w * rnd.triangular(0.6, 1.9, 1.1 if is_p else 0.95)
                w_candidate = min(max(w_candidate, 0.12e-6), 100e-6)
                ref = w_candidate if heavy_tail else base_w
                w_new = _quantize_like(w_candidate, ref, 0.005, 5e-9)
            l_new: Optional[float] = None
            if base_l > 0.0:
                l_candidate = max(base_l * rnd.triangular(0.9, 1.2, 1.03), 1e-9)
                l_new = _quantize_like(l_candidate, base_l, 0.002, 2e-9)
            for tok in parts:
                up = tok.upper()
                if up.startswith('W=') and w_like and w_new is not None:
                    tok = f"W={_float_to_unit(w_new, w_like, sig_digits=3)}"
                elif up.startswith('L=') and l_like and l_new is not None:
                    tok = f"L={_float_to_unit(l_new, l_like, sig_digits=3)}"
                new_parts.append(tok)
            dev_lines[0] = ' '.join(new_parts)
            return dev_lines
        # Capacitor: starts with C/c, format: Cname n1 n2 value [...]
        if s[0].lower() == 'c':
            parts = s.split()
            if len(parts) >= 4:
                like = parts[3]
                base = _unit_scale_to_float(like)
                if base > 0.0:
                    scale = rnd.uniform(0.7, 1.3)
                    newv = max(base * scale, 1e-18)
                    parts[3] = _float_to_unit(newv, like, sig_digits=3)
            dev_lines[0] = ' '.join(parts)
            return dev_lines
        return dev_lines

    devices = [jitter_device(d) for d in devices]
    # Shuffle devices order to reduce memorization (shuffle whole statement blocks)
    rnd.shuffle(devices)
    out_lines.extend(headers)
    for blk in subckts:
        out_lines.extend(blk)
    for stmt in devices:
        out_lines.extend(stmt)
    out_lines.extend(tails)
    out_lines.extend(footers)
    return '\n'.join(out_lines) + ('\n' if text.endswith('\n') else '')


def main():
    ap = argparse.ArgumentParser()
    # Back-compat: --model can be a single name or comma-separated list; prefer --models
    ap.add_argument(
        "--model",
        default=None,
        help="adapter spec (e.g., dummy or openai or openai:gpt-4o-mini). Comma-separated allowed; prefer --models.",
    )
    ap.add_argument(
        "--models",
        nargs="*",
        default=None,
        help="Space- or comma-separated list of adapter specs to evaluate (e.g., openai:gpt-4o-mini dummy)",
    )
    ap.add_argument("--split", default="dev", help="data split: train|dev|test")
    ap.add_argument("--max-items", type=int, default=0, help="limit items")
    ap.add_argument(
        "--family",
        choices=["analysis", "debugging", "design"],
        default=None,
        help="Limit to a specific evaluation family under data/<split>/<family>.",
    )
    ap.add_argument(
        "--family-subdir",
        dest="family_subdir",
        default=None,
        help="Optional subdirectory under the chosen family (e.g., feedback, filters, ota).",
    )
    ap.add_argument(
        "--item-index",
        type=int,
        default=0,
        help="1-based item index within the selected scope (after family filter). 0 = all.",
    )
    ap.add_argument(
        "--prompt-variant",
        dest="prompt_variant",
        choices=["short_form", "multiple_choice"],
        default=None,
        help="Filter questions by meta.prompt_variant. If unset, runs all variants.",
    )
    ap.add_argument(
        "--modality",
        dest="modality",
        default=None,
        help="Comma-separated modality filter (e.g., spice_netlist,cascode,casIR,veriloga). If unset, runs all modalities.",
    )
    ap.add_argument("--judge-model", "--judge_model", dest="judge_model", default=None, help="override judge model name")
    ap.add_argument("--model-workers", type=int, default=0, help="parallel model workers (0 = run all models in parallel)")
    ap.add_argument("--item-workers", type=int, default=8, help="per-model concurrent workers for items/questions (judge concurrency auto-scales with this if not explicitly set)")
    ap.add_argument(
        "--enable-profiling",
        action="store_true",
        help="Enable detailed performance profiling logs",
    )
    # Judge tuning
    ap.add_argument("--judge-rpm", type=float, default=None, help="Rate limit RPM for judge API (sets OPENAI_JUDGE_RPM)")
    ap.add_argument("--judge-tpm", type=float, default=None, help="Token per minute limit for judge API (sets OPENAI_JUDGE_TPM)")
    ap.add_argument("--judge-max-retries", type=int, default=None, help="Max retries for judge API (sets OPENAI_JUDGE_MAX_RETRIES)")
    ap.add_argument("--judge-concurrency", type=int, default=None, help="Max concurrent judge calls (sets OPENAI_JUDGE_CONCURRENCY). If unset, auto-scales with --item-workers to avoid bottlenecks.")
    args = ap.parse_args()
    # Judge is always enabled; no flag required

    profiling.set_enabled(args.enable_profiling)

    # Apply judge tuning via environment for scorer module
    if args.judge_rpm is not None:
        os.environ["OPENAI_JUDGE_RPM"] = str(args.judge_rpm)
    if args.judge_tpm is not None:
        os.environ["OPENAI_JUDGE_TPM"] = str(args.judge_tpm)
    if args.judge_max_retries is not None:
        os.environ["OPENAI_JUDGE_MAX_RETRIES"] = str(args.judge_max_retries)
    # Track if judge concurrency was explicitly set (via arg or pre-existing env var that wasn't auto-generated)
    # A value is explicit if: args.judge_concurrency is provided OR env var exists AND AUTO marker is not "1"
    judge_concurrency_explicitly_set = (
        args.judge_concurrency is not None
        or (bool(os.getenv("OPENAI_JUDGE_CONCURRENCY")) and os.getenv("OPENAI_JUDGE_CONCURRENCY_AUTO") != "1")
    )
    if args.judge_concurrency is not None:
        # Explicit override: set the value and remove/unset the AUTO marker
        os.environ["OPENAI_JUDGE_CONCURRENCY"] = str(args.judge_concurrency)
        os.environ.pop("OPENAI_JUDGE_CONCURRENCY_AUTO", None)
    else:
        # Adaptive judge concurrency: recompute if not explicitly set (or if it was auto-generated)
        # This ensures judge slots scale with parallelization capacity.
        # Performance note: With 8 item workers and only 3 judge slots, ~62% of threads block waiting.
        # By scaling judge concurrency to match workers (minus 2 for headroom), we reduce serialization.
        # If hitting rate limits, reduce via --judge-concurrency or configure OPENAI_JUDGE_RPM/TPM.
        adaptive_concurrency = max(3, args.item_workers - 2)
        os.environ["OPENAI_JUDGE_CONCURRENCY"] = str(adaptive_concurrency)
        os.environ["OPENAI_JUDGE_CONCURRENCY_AUTO"] = "1"

    # Load bench config (YAML)
    cfg = yaml.safe_load(Path("bench_config.yaml").read_text(encoding='utf-8')) or {}
    eval_cfg_raw = cfg.get("eval") or {}
    eval_cfg = eval_cfg_raw if isinstance(eval_cfg_raw, dict) else {}
    data_root = Path(cfg.get("paths", {}).get("data_root", "data"))
    # Prompts are referenced per-item: resolved as (item_dir/../prompts/<prompt_template>)
    outputs_root = Path(cfg.get("paths", {}).get("outputs_root", "outputs"))
    outputs_root.mkdir(parents=True, exist_ok=True)

    judge_reasoning_effort_cfg = eval_cfg.get("judge_reasoning_effort")
    if judge_reasoning_effort_cfg is not None and not os.getenv("OPENAI_JUDGE_REASONING_EFFORT"):
        os.environ["OPENAI_JUDGE_REASONING_EFFORT"] = str(judge_reasoning_effort_cfg)

    judge_model_cfg = eval_cfg.get("judge_model")
    judge_model_spec = args.judge_model if args.judge_model is not None else judge_model_cfg
    judge_model, judge_effort = normalize_judge_model(judge_model_spec)
    args.judge_model = judge_model
    # Store effort separately for judge calls (overrides env var if specified)
    if judge_effort:
        args.judge_reasoning_effort = judge_effort
    else:
        args.judge_reasoning_effort = None

    split_dir = data_root / args.split
    if not split_dir.exists():
        raise SystemExit(f"Split not found: {split_dir}")

    # Resolve model list (support both --models and legacy --model). If none, try bench_config eval.models.
    # This needs to happen before config table printing to show correct model count
    model_specs: List[str] = []
    if args.models:
        for token in args.models:
            if not token:
                continue
            model_specs.extend([t for t in token.split(",") if t])
    elif args.model:
        model_specs.extend([t for t in str(args.model).split(",") if t])
    else:
        cfg_models = eval_cfg.get("models") if isinstance(eval_cfg, dict) else None
        if isinstance(cfg_models, list) and cfg_models:
            model_specs = [str(m) for m in cfg_models]
        else:
            model_specs = ["dummy"]

    # Print configuration summary
    def _get_env_or_default(key: str, default: str = "not set") -> str:
        val = os.getenv(key)
        return val if val else default

    def _format_value(val: Any) -> str:
        if val is None:
            return "not set"
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, list):
            return ", ".join(str(v) for v in val)
        return str(val)

    config_table = Table(title="[bold cyan]Evaluation Configuration[/bold cyan]", show_header=True, header_style="bold")
    config_table.add_column("Category", style="cyan", no_wrap=True)
    config_table.add_column("Setting", style="yellow")
    config_table.add_column("Value", style="green")

    # Parallelization settings
    model_workers_display = str(args.model_workers) if args.model_workers > 0 else f"{len(model_specs)} (all)"
    config_table.add_row("Parallelization", "--model-workers", model_workers_display)
    config_table.add_row("", "--item-workers", str(args.item_workers))
    config_table.add_row("", "EVAL_MODEL_TIMEOUT", _get_env_or_default("EVAL_MODEL_TIMEOUT", "3600.0"))
    config_table.add_row("", "EVAL_ITEM_TIMEOUT", _get_env_or_default("EVAL_ITEM_TIMEOUT", "300.0"))

    # Judge settings
    judge_model_display = judge_model or _get_env_or_default("OPENAI_JUDGE_MODEL", _get_env_or_default("OPENAI_MODEL", "gpt-4o-mini"))
    config_table.add_row("Judge", "Model", judge_model_display)
    config_table.add_row("", "OPENAI_JUDGE_RPM", _get_env_or_default("OPENAI_JUDGE_RPM", "0 (unlimited)"))
    config_table.add_row("", "OPENAI_JUDGE_TPM", _get_env_or_default("OPENAI_JUDGE_TPM", "0 (unlimited)"))
    # Show judge concurrency with indication if it was auto-set
    judge_concurrency_val = os.getenv("OPENAI_JUDGE_CONCURRENCY", "")
    if judge_concurrency_val:
        if judge_concurrency_explicitly_set:
            # Explicitly set via --judge-concurrency or pre-existing env var
            judge_concurrency_display = judge_concurrency_val
        else:
            # Was auto-set adaptively
            judge_concurrency_display = f"{judge_concurrency_val} (auto-set from --item-workers)"
    else:
        judge_concurrency_display = "10 (default)"
    config_table.add_row("", "OPENAI_JUDGE_CONCURRENCY", judge_concurrency_display)
    config_table.add_row("", "OPENAI_JUDGE_MAX_RETRIES", _get_env_or_default("OPENAI_JUDGE_MAX_RETRIES", "6"))
    config_table.add_row("", "OPENAI_JUDGE_BACKOFF_BASE", _get_env_or_default("OPENAI_JUDGE_BACKOFF_BASE", "1.0"))
    config_table.add_row("", "OPENAI_JUDGE_TIMEOUT", _get_env_or_default("OPENAI_JUDGE_TIMEOUT", _get_env_or_default("OPENAI_TIMEOUT", "60.0")))
    config_table.add_row("", "OPENAI_JUDGE_TEMPERATURE", _get_env_or_default("OPENAI_JUDGE_TEMPERATURE", "0.0"))
    judge_max_tokens_default = "2000" if "gpt-5" in judge_model_display.lower() else "400"
    config_table.add_row("", "OPENAI_JUDGE_MAX_TOKENS", _get_env_or_default("OPENAI_JUDGE_MAX_TOKENS", judge_max_tokens_default))
    config_table.add_row("", "OPENAI_JUDGE_REASONING_EFFORT", _get_env_or_default("OPENAI_JUDGE_REASONING_EFFORT", "not set"))
    config_table.add_row("", "OPENAI_JUDGE_TOKEN_DIVISOR", _get_env_or_default("OPENAI_JUDGE_TOKEN_DIVISOR", "3.5"))

    # OpenAI adapter settings
    config_table.add_row("OpenAI Adapter", "OPENAI_RPM", _get_env_or_default("OPENAI_RPM", "0 (unlimited)"))
    config_table.add_row("", "OPENAI_TPM", _get_env_or_default("OPENAI_TPM", "0 (unlimited)"))
    config_table.add_row("", "OPENAI_MAX_RETRIES", _get_env_or_default("OPENAI_MAX_RETRIES", "8"))
    config_table.add_row("", "OPENAI_BACKOFF_BASE", _get_env_or_default("OPENAI_BACKOFF_BASE", "1.0"))
    config_table.add_row("", "OPENAI_TIMEOUT", _get_env_or_default("OPENAI_TIMEOUT", "60.0"))
    config_table.add_row("", "OPENAI_MODEL", _get_env_or_default("OPENAI_MODEL", "gpt-4o-mini"))
    config_table.add_row("", "OPENAI_TEMPERATURE", _get_env_or_default("OPENAI_TEMPERATURE", str(eval_cfg.get("temperature", 0.2))))
    config_table.add_row("", "OPENAI_MAX_TOKENS", _get_env_or_default("OPENAI_MAX_TOKENS", str(eval_cfg.get("max_tokens", 800))))
    config_table.add_row("", "OPENAI_TOKEN_DIVISOR", _get_env_or_default("OPENAI_TOKEN_DIVISOR", "4"))

    # Anthropic adapter settings
    config_table.add_row("Anthropic Adapter", "ANTHROPIC_RPM", _get_env_or_default("ANTHROPIC_RPM", "0 (unlimited)"))
    config_table.add_row("", "ANTHROPIC_TPM", _get_env_or_default("ANTHROPIC_TPM", "0 (unlimited)"))
    config_table.add_row("", "ANTHROPIC_MAX_RETRIES", _get_env_or_default("ANTHROPIC_MAX_RETRIES", "8"))
    config_table.add_row("", "ANTHROPIC_BACKOFF_BASE", _get_env_or_default("ANTHROPIC_BACKOFF_BASE", "1.0"))
    config_table.add_row("", "ANTHROPIC_MODEL", _get_env_or_default("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"))
    config_table.add_row("", "ANTHROPIC_TEMPERATURE", _get_env_or_default("ANTHROPIC_TEMPERATURE", str(eval_cfg.get("temperature", 0.2))))
    config_table.add_row("", "ANTHROPIC_MAX_TOKENS", _get_env_or_default("ANTHROPIC_MAX_TOKENS", str(eval_cfg.get("max_tokens", 800))))
    config_table.add_row("", "ANTHROPIC_TOKEN_DIVISOR", _get_env_or_default("ANTHROPIC_TOKEN_DIVISOR", "4"))

    # Google adapter settings
    config_table.add_row("Google Adapter", "GOOGLE_RPM", _get_env_or_default("GOOGLE_RPM", "0 (unlimited)"))
    config_table.add_row("", "GOOGLE_TPM", _get_env_or_default("GOOGLE_TPM", "0 (unlimited)"))
    config_table.add_row("", "GOOGLE_MAX_RETRIES", _get_env_or_default("GOOGLE_MAX_RETRIES", "8"))
    config_table.add_row("", "GOOGLE_BACKOFF_BASE", _get_env_or_default("GOOGLE_BACKOFF_BASE", "1.0"))
    config_table.add_row("", "GOOGLE_TIMEOUT", _get_env_or_default("GOOGLE_TIMEOUT", "60.0"))
    config_table.add_row("", "GOOGLE_MODEL", _get_env_or_default("GOOGLE_MODEL", "gemini-2.5-pro"))
    config_table.add_row("", "GOOGLE_TEMPERATURE", _get_env_or_default("GOOGLE_TEMPERATURE", str(eval_cfg.get("temperature", 0.2))))
    config_table.add_row("", "GOOGLE_MAX_TOKENS", _get_env_or_default("GOOGLE_MAX_TOKENS", str(eval_cfg.get("max_tokens", 800))))
    config_table.add_row("", "GOOGLE_TOKEN_DIVISOR", _get_env_or_default("GOOGLE_TOKEN_DIVISOR", "4"))
    config_table.add_row("", "GOOGLE_THINKING_BUDGET", _get_env_or_default("GOOGLE_THINKING_BUDGET", "0"))

    # OpenRouter adapter settings
    config_table.add_row("OpenRouter Adapter", "OPENROUTER_RPM", _get_env_or_default("OPENROUTER_RPM", "0 (unlimited)"))
    config_table.add_row("", "OPENROUTER_TPM", _get_env_or_default("OPENROUTER_TPM", "0 (unlimited)"))
    config_table.add_row("", "OPENROUTER_MAX_RETRIES", _get_env_or_default("OPENROUTER_MAX_RETRIES", "8"))
    config_table.add_row("", "OPENROUTER_BACKOFF_BASE", _get_env_or_default("OPENROUTER_BACKOFF_BASE", "1.0"))
    config_table.add_row("", "OPENROUTER_MODEL", _get_env_or_default("OPENROUTER_MODEL", "openai/gpt-4o-mini"))
    config_table.add_row("", "OPENROUTER_TEMPERATURE", _get_env_or_default("OPENROUTER_TEMPERATURE", str(eval_cfg.get("temperature", 0.2))))
    config_table.add_row("", "OPENROUTER_MAX_TOKENS", _get_env_or_default("OPENROUTER_MAX_TOKENS", str(eval_cfg.get("max_tokens", 800))))
    config_table.add_row("", "OPENROUTER_TOKEN_DIVISOR", _get_env_or_default("OPENROUTER_TOKEN_DIVISOR", "4"))
    config_table.add_row("", "OPENROUTER_REFERER", _get_env_or_default("OPENROUTER_REFERER", "not set"))
    config_table.add_row("", "OPENROUTER_TITLE", _get_env_or_default("OPENROUTER_TITLE", "not set"))

    # Config file settings
    config_table.add_row("Config File", "eval.max_tokens", _format_value(eval_cfg.get("max_tokens")))
    config_table.add_row("", "eval.temperature", _format_value(eval_cfg.get("temperature")))
    config_table.add_row("", "eval.top_p", _format_value(eval_cfg.get("top_p")))
    config_table.add_row("", "eval.judge_model", _format_value(eval_cfg.get("judge_model")))
    config_table.add_row("", "eval.models", _format_value(eval_cfg.get("models")))
    config_table.add_row("", "eval.judge_reasoning_effort", _format_value(eval_cfg.get("judge_reasoning_effort")))

    # Models being evaluated
    models_display = ", ".join(model_specs) if model_specs else "dummy"
    config_table.add_row("Models", "Models to evaluate", models_display)

    # Other settings
    config_table.add_row("Other", "--enable-profiling", "enabled" if args.enable_profiling else "disabled")
    config_table.add_row("", "--split", args.split)
    config_table.add_row("", "--max-items", str(args.max_items) if args.max_items > 0 else "unlimited")
    config_table.add_row("", "--family", args.family or "all")
    config_table.add_row("", "--family-subdir", args.family_subdir or "not set")
    config_table.add_row("", "--item-index", str(args.item_index) if args.item_index > 0 else "all")

    print(config_table)
    print()  # Empty line after table

    dummy_requested = False
    for spec in model_specs:
        clean_spec = spec.strip()
        if not clean_spec:
            continue
        if parse_model_spec(clean_spec)[0] == "dummy":
            dummy_requested = True
            break
    judge_is_dummy = args.judge_model == "dummy"
    if dummy_requested and not judge_is_dummy:
        judge_display = args.judge_model or os.getenv("OPENAI_JUDGE_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        msg = (
            f"[run_eval] --model dummy selected, but judge model is '{judge_display}'.\n"
            "\033[31mRunning a dummy model with a real judge will consume API tokens.\033[0m\n"
            "Hint: rerun with --judge_model dummy if you want a zero-cost judge.\n"
            "Proceed anyway? [y/N]: "
        )
        if not sys.stdin.isatty():
            raise SystemExit("Aborting: set --judge_model dummy to avoid real judge in non-interactive mode.")
        try:
            confirm = input(msg)
        except EOFError:
            raise SystemExit("Aborting: confirmation required to run dummy model with real judge.")
        if confirm.strip().lower() not in {"y", "yes"}:
            print("Aborting per user selection.", flush=True)
            return

    # Build adapters map keyed by a printable slug
    adapters: Dict[str, Any] = {}
    model_slugs: List[str] = []
    for spec in model_specs:
        name, kwargs = parse_model_spec(spec)
        adapter = get_adapter(name, **kwargs)
        # Create a unique, descriptive slug for outputs
        # Include effort level in slug if specified for uniqueness
        effort_suffix = ""
        if kwargs.get("reasoning_effort"):
            effort_suffix = f"_{kwargs['reasoning_effort']}"
        elif kwargs.get("thinking_budget"):
            effort_suffix = f"_{kwargs['thinking_budget']}"
        if kwargs.get("model"):
            slug = f"{name}_{kwargs['model']}{effort_suffix}".replace("/", "-")
        else:
            slug = f"{name}{effort_suffix}"
        # Ensure uniqueness if duplicates
        base_slug = slug
        suffix = 2
        while slug in adapters:
            slug = f"{base_slug}_{suffix}"
            suffix += 1
        adapters[slug] = adapter
        model_slugs.append(slug)

    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    out_dir = outputs_root / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Combined results file for convenience/back-compat
    results_path = out_dir / "combined_results.jsonl"

    # Scope items by optional family (e.g., debugging, analysis, design)
    search_root = split_dir if not args.family else (split_dir / args.family)
    if args.family_subdir:
        search_root = search_root / args.family_subdir
    if not search_root.exists():
        raise SystemExit(f"Scope not found: {search_root}")
    items = iter_items(search_root)
    # Optional 1-based item index selection
    if args.item_index and args.item_index > 0:
        if args.item_index > len(items):
            raise SystemExit(f"item-index {args.item_index} exceeds available items ({len(items)}) in {search_root}")
        items = [items[args.item_index - 1]]
    if args.max_items and args.max_items > 0:
        items = items[: args.max_items]

    # Optional filtering by prompt variant and/or modality (reduces number of model calls)
    allowed_modalities: Optional[set[str]] = None
    if args.modality and str(args.modality).strip():
        allowed_modalities = {m.strip() for m in str(args.modality).split(",") if m.strip()}

    def _prompt_variant_of(q: "Question") -> str:
        try:
            pv = (q.meta or {}).get("prompt_variant")
            return pv if pv in {"short_form", "multiple_choice"} else "short_form"
        except Exception:
            return "short_form"

    if args.prompt_variant or allowed_modalities is not None:
        filtered_items: List[EvalItem] = []
        for it in items:
            qs = it.questions
            if args.prompt_variant:
                qs = [q for q in qs if _prompt_variant_of(q) == args.prompt_variant]
            if allowed_modalities is not None:
                qs = [q for q in qs if getattr(q, "modality", None) in allowed_modalities]
            if qs:
                it.questions = qs
                filtered_items.append(it)
        items = filtered_items

    if not items or sum(len(it.questions) for it in items) == 0:
        raise SystemExit("No questions matched the selected scope/filters (family/family-subdir/item-index/prompt-variant/modality).")

    # Pre-compute totals for progress bars
    total_questions = sum(len(it.questions) for it in items)
    total = 0

    # Create per-model result writers
    model_files: Dict[str, Any] = {}
    for slug in model_slugs:
        mdir = out_dir / slug
        mdir.mkdir(parents=True, exist_ok=True)
        model_files[slug] = (mdir / "results.jsonl").open("w")

    scope_msg = f" split=[bold]{args.split}[/bold]"
    if args.family:
        scope_msg += f" family=[bold]{args.family}[/bold]"
    if args.family_subdir:
        scope_msg += f" subdir=[bold]{args.family_subdir}[/bold]"
    if args.item_index and args.item_index > 0:
        scope_msg += f" item-index=[bold]{args.item_index}[/bold]"
    print(f"[cyan]Evaluating[/cyan]{scope_msg} on models: {', '.join(model_slugs)}")

    write_lock = threading.Lock()
    progress_lock = threading.Lock()
    # No rubric lock: deterministic rubric scoring removed

    def inject_device_swap_spice(text: str, seed: int):
        """Randomly swap one MOSFET device type: NMOS<->PMOS or nch<->pch.
        Returns (mutated_text, swapped_id, from_type, to_type). If no eligible
        devices found, returns (text, None, None, None).
        """
        rnd = random.Random(seed)
        lines = text.splitlines()
        # Find eligible MOS lines and parse tokens
        candidates = []  # (index, id, model_token_index, model_token_value)
        for idx, raw in enumerate(lines):
            s = raw.strip()
            if not s or s.startswith(('*', ';', '//')):
                continue
            # Simple SPICE: MOS line starts with 'M'
            if not s or s[0].upper() != 'M':
                continue
            # Respect inline comments: split off any '//' or ';' trailing comment
            cpos = len(s)
            p2 = s.find('//')
            if p2 != -1:
                cpos = min(cpos, p2)
            p3 = s.find(';')
            if p3 != -1:
                cpos = min(cpos, p3)
            code = s[:cpos]
            comment_tail = s[cpos:]
            # Tokenize code segment only
            parts = code.split()
            if not parts:
                continue
            dev_id = parts[0]
            # Model token is typically the 6th token for 4-terminal + model name
            # But be flexible: search for first token equal to nmos/pmos/nch/pch
            model_idx = None
            model_val = None
            for j, tok in enumerate(parts[1:], start=1):
                t = tok.strip()
                tl = t.lower()
                if tl in ("nch", "pch", "nmos", "pmos"):
                    model_idx = j
                    model_val = t
                    break
            if model_idx is None or not model_val:
                continue
            candidates.append((idx, dev_id, model_idx, model_val))

        if not candidates:
            return text, None, None, None
        # Pick a device deterministically
        pick = rnd.choice(candidates)
        idx, dev_id, model_idx, model_val = pick
        parts = lines[idx].strip().split()
        old = parts[model_idx]
        tl = old.lower()
        if tl in ("nch", "nmos"):
            new = "pch" if tl == "nch" else ("PMOS" if old.isupper() else "pmos")
            from_type, to_type = "NMOS", "PMOS"
        elif tl in ("pch", "pmos"):
            new = "nch" if tl == "pch" else ("NMOS" if old.isupper() else "nmos")
            from_type, to_type = "PMOS", "NMOS"
        else:
            return text, None, None, None
        parts[model_idx] = new
        # Rebuild line, preserving any inline comment tail
        code_new = " ".join(parts)
        # Preserve newline character at line end via join later
        lines[idx] = code_new + comment_tail
        return "\n".join(lines) + ("\n" if text.endswith("\n") else ""), dev_id, from_type, to_type

    def _strip_json_comments(s: str) -> str:
        """Remove // line comments and /* */ block comments from JSON-like text.
        Preserves content inside quoted strings. Intended for casIR artifacts
        that allow comments but are otherwise valid JSON.
        """
        out_chars: list[str] = []
        in_str = False
        str_ch = ''
        esc = False
        i = 0
        n = len(s)
        in_line = False
        in_block = False
        while i < n:
            ch = s[i]
            ch2 = s[i+1] if i+1 < n else ''
            if in_line:
                if ch == '\n':
                    in_line = False
                    out_chars.append(ch)
                i += 1
                continue
            if in_block:
                if ch == '*' and ch2 == '/':
                    in_block = False
                    i += 2
                else:
                    i += 1
                continue
            if not in_str and ch == '/' and ch2 == '/':
                in_line = True
                i += 2
                continue
            if not in_str and ch == '/' and ch2 == '*':
                in_block = True
                i += 2
                continue
            out_chars.append(ch)
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == str_ch:
                    in_str = False
            else:
                if ch in ('"', "'"):
                    in_str = True
                    str_ch = ch
            i += 1
        return ''.join(out_chars)

    def inject_device_swap_casir(text: str, seed: int):
        """Swap the polarity of a single MOS-like motif in a casIR JSON artifact.
        Looks for motif.type containing 'NMOS' or 'PMOS' (case-insensitive) and flips it.
        Returns (mutated_text, swapped_id, from_type, to_type). If none found, returns
        (text, None, None, None).
        """
        try:
            data = json.loads(_strip_json_comments(text))
        except Exception:
            return text, None, None, None
        motifs = data.get("motifs") or []
        candidates = []  # (index, id, type)
        for i, m in enumerate(motifs):
            if not isinstance(m, dict):
                continue
            mid = str(m.get("id", "")).strip()
            mtype = str(m.get("type", "")).strip()
            if not mid or not mtype:
                continue
            lt = mtype.lower()
            if ("nmos" in lt) or ("pmos" in lt):
                candidates.append((i, mid, mtype))
        if not candidates:
            return text, None, None, None
        rnd = random.Random(seed)
        idx, mid, mtype = rnd.choice(candidates)
        lt = mtype.lower()
        if "nmos" in lt and "pmos" not in lt:
            new_type = mtype.replace("NMOS", "PMOS").replace("nmos", "pmos")
            from_type, to_type = "NMOS", "PMOS"
        elif "pmos" in lt and "nmos" not in lt:
            new_type = mtype.replace("PMOS", "NMOS").replace("pmos", "nmos")
            from_type, to_type = "PMOS", "NMOS"
        else:
            # If both appear or ambiguous, flip the first occurrence preference NMOS->PMOS
            if lt.find("nmos") <= lt.find("pmos"):
                new_type = mtype.replace("NMOS", "PMOS").replace("nmos", "pmos")
                from_type, to_type = "NMOS", "PMOS"
            else:
                new_type = mtype.replace("PMOS", "NMOS").replace("pmos", "nmos")
                from_type, to_type = "PMOS", "NMOS"
        try:
            data["motifs"][idx]["type"] = new_type
        except Exception:
            return text, None, None, None
        mutated = json.dumps(data, indent=2)
        if text.endswith("\n"):
            mutated += "\n"
        return mutated, mid, from_type, to_type

    def inject_device_swap_cascode(text: str, seed: int):
        """Swap one MOS polarity in ADL/"cascode" artifact by flipping NMOS<->PMOS
        in motif type tokens (e.g., DiffPairNMOS <-> DiffPairPMOS). Ignores comments
        and targets identifiers in code contexts: after 'new', after 'attach', or
        identifiers used as call/constructor names (followed by '(') or assignment RHS.
        Returns (mutated_text, swapped_label, from_type, to_type).
        """
        lines = text.splitlines()
        import re
        ident_pat = re.compile(r"\b((?:[A-Za-z_][A-Za-z0-9_]*?)?(?:NMOS|PMOS)(?:[A-Za-z0-9_]*)?)\b")
        candidates = []  # (line_idx, span, full_token)
        for i, raw in enumerate(lines):
            # Ignore everything after '//' (treat as comment)
            code = raw.split('//', 1)[0]
            for m in ident_pat.finditer(code):
                token = m.group(1)
                s, e = m.span(1)
                before = code[:s]
                after = code[e:]
                # Heuristic contexts to ensure we mutate code, not prose:
                ctx_new = bool(re.search(r"\bnew\s+$", before))
                ctx_attach = bool(re.search(r"\battach\s+$", before))
                ctx_call = bool(re.match(r"\s*\(", after))
                ctx_assign = bool(re.search(r"=\s*$", before))
                if ctx_new or ctx_attach or ctx_call or ctx_assign:
                    candidates.append((i, (s, e), token))
        if not candidates:
            return text, None, None, None
        rnd = random.Random(seed)
        i, (s, e), token = rnd.choice(candidates)
        if token.lower().endswith("nmos"):
            new_token = token[:-4] + "PMOS"
            from_type, to_type = "NMOS", "PMOS"
        else:
            new_token = token[:-4] + "NMOS"
            from_type, to_type = "PMOS", "NMOS"
        # Replace within the chosen line
        line = lines[i]
        lines[i] = line[:s] + new_token + line[e:]
        # Try to infer a nearby label/id for reporting (e.g., lhs var before '=')
        swapped_label = token
        try:
            code = line.split('//', 1)[0]
            m2 = re.search(r"\b([A-Za-z0-9_]+)\s*=\s*new\s+", code)
            if m2:
                swapped_label = m2.group(1)
            else:
                m3 = re.search(r"attach\s+[A-Za-z0-9_]+\s+on\s+([A-Za-z0-9_]+)", code)
                if m3:
                    swapped_label = m3.group(1)
        except Exception:
            pass
        mutated = "\n".join(lines)
        if text.endswith("\n"):
            mutated += "\n"
        return mutated, swapped_label, from_type, to_type

    def run_for_model(slug: str):
        nonlocal total
        adapter = adapters[slug]
        # Validate adapter is actually an adapter object, not a string
        if not hasattr(adapter, 'predict'):
            raise TypeError(f"Expected adapter object for '{slug}', got {type(adapter).__name__}: {adapter}")
        if not hasattr(adapter, 'name'):
            raise TypeError(f"Adapter object for '{slug}' missing 'name' attribute: {type(adapter).__name__}")
        task_id = model_tasks[slug]

        def process_q(it: EvalItem, q: Question):
            import traceback  # Ensure traceback is available in nested function scope
            nonlocal total
            item_timer = perf_counter() if profiling.is_enabled() else None
            item_dir = Path(it.item_dir)
            inv_ids = it.inventory.all_ids()
            # Prompt
            if not q.prompt_template:
                raise SystemExit(f"Question {q.id} must specify prompt_template (relative path, e.g., ../prompts/design_ota.txt): {item_dir}")
            # Resolve prompt_template relative to item_dir (e.g., ../prompts/design_ota.txt from item_dir)
            ppath = (item_dir / q.prompt_template).resolve()
            if not ppath.exists():
                raise SystemExit(
                    f"Prompt template not found for {q.id}:\n"
                    f"  Expected path: {ppath}\n"
                    f"  Resolved from: {item_dir} / {q.prompt_template}\n"
                    f"  Item directory: {item_dir}"
                )
            def _display_modality(mod: str) -> str:
                # Human-friendly modality name for prompts to avoid confusion
                if mod == "cascode":
                    return "analog description language"
                if mod == "spice_netlist":
                    return "SPICE netlist"
                if mod == "casIR":
                    return "casIR"
                return mod
            # For design track, switch prompt template based on modality to include examples and modality-specific guidance
            if str(q.track).lower() == "design":
                # Default to existing template for SPICE
                if q.modality == "casIR":
                    ppath = (item_dir.parent / "prompts" / "design_ota_casir.txt")
                elif q.modality == "cascode":
                    ppath = (item_dir.parent / "prompts" / "design_ota_cas.txt")
            prompt_tmpl = ppath.read_text(encoding='utf-8')
            # Build example blocks for casIR/cascode modalities
            examples = ""
            # Build or load a plain-language design brief to tell the model exactly what to design
            def _design_brief() -> str:
                # Prefer a local design_brief.txt alongside the item questions
                try:
                    db_path = item_dir / "design_brief.txt"
                    if db_path.exists():
                        txt = db_path.read_text(encoding='utf-8').strip()
                        if txt:
                            return txt
                except Exception:
                    pass
                # If no brief is present, fail fast so datasets stay explicit
                raise SystemExit(f"design_brief.txt not found for design item: {item_dir}")
            # Only require a design brief for design track; other families do not need it
            if str(q.track).lower() == "design":
                design_brief = _design_brief()
            else:
                design_brief = ""

            # For feedback design tasks, include the template netlist in the prompt but blank out
            # value fields so the model must fill in parameters (R/C values) while keeping topology fixed.
            template_netlist = ""
            if str(q.track).lower() == "design" and "design/feedback" in str(item_dir).replace("\\", "/"):
                try:
                    tpl_path = (item_dir / q.artifact_path)
                    if tpl_path.exists():
                        raw_tpl = tpl_path.read_text(encoding="utf-8").strip()
                        # Blank last token on R*/C* lines: `R1 n1 n2 10k` -> `R1 n1 n2 BLANK`
                        # Also covers symbolic placeholders like `R` or `C`.
                        blanked_lines = []
                        for raw in raw_tpl.splitlines():
                            s = raw.strip()
                            if not s or s.startswith(("*", ";", "//")):
                                blanked_lines.append(raw)
                                continue
                            parts = s.split()
                            if len(parts) >= 4 and parts[0] and parts[0][0].upper() in {"R", "C"}:
                                # preserve original indentation by rebuilding from raw prefix
                                leading = raw[: len(raw) - len(raw.lstrip())]
                                parts[-1] = "BLANK"
                                blanked_lines.append(leading + " ".join(parts))
                            else:
                                blanked_lines.append(raw)
                        template_netlist = "\n".join(blanked_lines).strip()
                except Exception:
                    template_netlist = ""
            
            # Multiple choice support: load MC answer key and format choices
            choices = ""
            mc_answer_key = None
            prompt_variant = q.meta.get("prompt_variant", "short_form")
            mc_choices_token = "__MC_CHOICES__"
            # If we rename instance names for MC artifacts, store the mapping so we can
            # update any choices that reference those instance names.
            mc_instance_rename_map: Dict[str, str] = {}
            if prompt_variant == "multiple_choice":
                # Load MC answer key based on aspect
                aspect = q.meta.get("aspect", "")
                mc_key_name = "mc_answer_key.json"
                if aspect and str(q.track).lower() == "analysis":
                    mc_key_name = f"mc_answer_key_{aspect}.json"
                
                mc_key_path = item_dir / mc_key_name
                if mc_key_path.exists():
                    try:
                        mc_answer_key = json.loads(mc_key_path.read_text(encoding='utf-8'))
                        # Defer rendering choices until after artifact is finalized (MCQs may
                        # substitute placeholder device IDs based on the attached netlist).
                        choices = mc_choices_token
                    except Exception as e:
                        print(f"Warning: Could not load MC answer key for {q.id}: {e}", file=sys.stderr)
                        choices = "(MC choices unavailable)"
                else:
                    print(f"Warning: MC answer key not found for {q.id} at {mc_key_path}", file=sys.stderr)
                    choices = "(MC choices unavailable)"
            if str(q.track).lower() == "design" and q.modality in ("casIR", "cascode"):
                try:
                    # Canonical examples: ota003 and ota006 from templates
                    base003 = Path("data/dev/templates/ota/ota003")
                    base006 = Path("data/dev/templates/ota/ota006")
                    if q.modality == "casIR":
                        ex1 = (base003 / "netlist.cir").read_text(encoding='utf-8')
                        ex2 = (base006 / "netlist.cir").read_text(encoding='utf-8')
                        examples = (
                            "Example 1 (ota003):\n```json\n" + ex1.strip() + "\n```\n\n" +
                            "Example 2 (ota006):\n```json\n" + ex2.strip() + "\n```\n"
                        )
                    else:
                        # cascode (analog description language)
                        ex1 = (base003 / "netlist.cas").read_text(encoding='utf-8')
                        ex2 = (base006 / "netlist.cas").read_text(encoding='utf-8')
                        examples = (
                            "Example 1 (ota003):\n```text\n" + ex1.strip() + "\n```\n\n" +
                            "Example 2 (ota006):\n```text\n" + ex2.strip() + "\n```\n"
                        )
                except Exception:
                    examples = ""
            try:
                prompt = prompt_tmpl.format(
                    modality=_display_modality(q.modality),
                    examples=examples,
                    design_brief=design_brief,
                    template_netlist=template_netlist,
                    choices=choices,
                )
            except Exception:
                # Back-compat: older templates may not use {examples} or {choices}
                try:
                    prompt = prompt_tmpl.format(
                        modality=_display_modality(q.modality),
                        design_brief=design_brief,
                        template_netlist=template_netlist,
                        choices=choices,
                    )
                except Exception:
                    try:
                        prompt = prompt_tmpl.format(
                            modality=_display_modality(q.modality),
                            template_netlist=template_netlist,
                            choices=choices,
                        )
                    except Exception:
                        prompt = prompt_tmpl.format(modality=_display_modality(q.modality), template_netlist=template_netlist)

            # Collect attachment file paths to pass to adapter
            attachment_paths = []
            if q.attachments:
                prompt += "\n\n**Attached Files:**\n"
                for att in q.attachments:
                    att_path = item_dir / att.get("path", "")
                    if att_path.exists():
                        desc = att.get("description", att_path.name)
                        
                        # For large files (Gm/ID tables), pass to adapter as file attachment
                        if att_path.stat().st_size > 100_000:  # >100KB
                            prompt += f"\n- **{att_path.name}**: {desc}\n"
                            prompt += f"  (Full file attached, {att_path.stat().st_size:,} bytes)\n"
                            attachment_paths.append(str(att_path.absolute()))
                        else:
                            # Small files: include full content in prompt
                            att_content = att_path.read_text(encoding='utf-8')
                            prompt += f"\n**{att_path.name}**:\n```\n{att_content}\n```\n"

            # Artifact
            art_path = item_dir / q.artifact_path
            artifact_text = ""
            if art_path.exists():
                try:
                    artifact_text = art_path.read_text(encoding='utf-8')
                except Exception:
                    artifact_text = ""
            artifact_used = artifact_text
            # For design track, do not leak template artifacts to the model prompt
            if str(q.track).lower() == "design":
                artifact_used = ""
            rand_info: Dict[str, Any] = {}
            
            # Helper functions for template loading and seed computation
            def _load_template_text(modality: str, fallback: str) -> str:
                """Load template text from meta.json template_path, or return fallback."""
                meta_path = item_dir / "meta.json"
                if not meta_path.exists():
                    return fallback
                try:
                    m = json.loads(meta_path.read_text(encoding='utf-8'))
                    tpath = m.get("template_path") or m.get("template")
                    if not isinstance(tpath, str) or not tpath.strip():
                        return fallback
                    tdir = (item_dir / tpath).resolve()
                    ext_map = {"spice_netlist": "sp", "casIR": "cir", "cascode": "cas"}
                    template_file = tdir / f"netlist.{ext_map.get(modality, 'sp')}"
                    if template_file.exists():
                        # Try UTF-8 first, then UTF-16 if that fails
                        try:
                            return template_file.read_text(encoding='utf-8')
                        except UnicodeDecodeError:
                            return template_file.read_text(encoding='utf-16')
                except Exception:
                    pass
                return fallback

            def _template_artifact_path(modality: str) -> Optional[Path]:
                """Return absolute path to canonical template artifact (if available)."""
                meta_path = item_dir / "meta.json"
                if not meta_path.exists():
                    return None
                try:
                    m = json.loads(meta_path.read_text(encoding='utf-8'))
                    tpath = m.get("template_path") or m.get("template")
                    if not isinstance(tpath, str) or not tpath.strip():
                        return None
                    tdir = (item_dir / tpath).resolve()
                    ext_map = {"spice_netlist": "sp", "casIR": "cir", "cascode": "cas"}
                    template_file = tdir / f"netlist.{ext_map.get(modality, 'sp')}"
                    return template_file if template_file.exists() else None
                except Exception:
                    return None
            
            def _get_meta_seed() -> int:
                """Get gen_seed from meta.json or compute from item_dir hash."""
                mpath = item_dir / "meta.json"
                if mpath.exists():
                    try:
                        mm = json.loads(mpath.read_text(encoding='utf-8'))
                        ms = mm.get("gen_seed")
                        if isinstance(ms, int):
                            return ms
                    except Exception:
                        pass
                return int.from_bytes(hashlib.sha256(str(item_dir).encode()).digest()[:8], 'big')
            
            # Debugging support: generate bugged artifact from template if requested
            bug_info: Dict[str, Any] = {}
            if str(q.track).lower() == "debugging" and q.judge_id == "debug_device_swap":
                def _inject_device_swap(
                    modality: str,
                    inject_func,
                    error_guidance: str
                ) -> None:
                    """Inject device swap bug and update artifact_used/bug_info."""
                    nonlocal artifact_used, bug_info, art_path
                    ext_map = {"spice_netlist": "sp", "casIR": "cir", "cascode": "cas"}
                    ext = ext_map.get(modality, "sp")
                    
                    base_text = _load_template_text(modality, artifact_text)
                    meta_seed = _get_meta_seed()
                    bug_seed = int.from_bytes(
                        hashlib.sha256(f"{meta_seed}:{Path(it.item_dir).name}:{q.id}:bug".encode()).digest()[:8],
                        'big'
                    )
                    mutated, dev_id, from_t, to_t = inject_func(base_text or "", bug_seed)
                    if dev_id:
                        artifact_used = mutated
                        bug_info = {"bug_type": "device_polarity_swap", "swapped_id": dev_id, "from_type": from_t, "to_type": to_t}
                        try:
                            bug_path = item_dir / f"netlist_bug.{ext}"
                            bug_path.write_text(artifact_used, encoding='utf-8')
                            art_path = bug_path
                        except Exception:
                            pass
                    else:
                        raise SystemExit(
                            f"No eligible devices found for device swap injection in {q.id} "
                            f"(modality: {modality}, item: {item_dir}). {error_guidance}"
                        )
                
                if q.modality == "spice_netlist":
                    _inject_device_swap(
                        q.modality,
                        inject_device_swap_spice,
                        "Check that the template/netlist contains MOS devices with NMOS/PMOS or nch/pch model types."
                    )
                elif q.modality == "casIR":
                    _inject_device_swap(
                        q.modality,
                        inject_device_swap_casir,
                        "Check that the template/netlist contains motifs with NMOS/PMOS types."
                    )
                elif q.modality == "cascode":
                    _inject_device_swap(
                        q.modality,
                        inject_device_swap_cascode,
                        "Check that the template/netlist contains NMOS/PMOS identifiers in code contexts."
                    )

            # For analysis track, always use canonical template artifacts (no randomization/shuffling),
            # so the model sees the exact reference netlist under data/<split>/templates/...
            if str(q.track).lower() == "analysis":
                tpl_ap = _template_artifact_path(q.modality)
                if tpl_ap is not None:
                    art_path = tpl_ap
                    artifact_used = _load_template_text(q.modality, artifact_used)
                    rand_info = {"source": "template"}

            # For MCQs, attach a template SPICE netlist with SHUFFLED transistor instance names
            # (topology unchanged). This enables distractors that swap the wrong subscript.
            if (
                str(q.track).lower() == "analysis"
                and (q.meta or {}).get("prompt_variant") == "multiple_choice"
                and q.modality == "spice_netlist"
                and artifact_used
            ):
                def _shuffle_instance_names(
                    netlist: str,
                    seed: int,
                    prefixes: tuple[str, ...],
                ) -> tuple[str, dict[str, str]]:
                    """
                    Rename instance names (first token) for specified prefixes without changing topology.
                    IMPORTANT: we rename EVERY matched instance to a fresh new name (not just shuffle),
                    so the output visibly changes and doesn't accidentally keep many original IDs.
                    """
                    import re
                    import random

                    rnd = random.Random(seed)
                    lines = netlist.splitlines()

                    # Collect instance IDs per prefix (preserve first-seen order)
                    ids_by_pref: dict[str, list[str]] = {p: [] for p in prefixes}
                    seen_by_pref: dict[str, set[str]] = {p: set() for p in prefixes}
                    for ln in lines:
                        s = ln.lstrip()
                        if not s:
                            continue
                        head = s.split(None, 1)[0]
                        if not head:
                            continue
                        pref = head[:1].upper()
                        if pref in ids_by_pref and head not in seen_by_pref[pref]:
                            ids_by_pref[pref].append(head)
                            seen_by_pref[pref].add(head)

                    # Build mapping
                    mapping: dict[str, str] = {}
                    all_existing = {s.split(None, 1)[0] for s in lines if s.strip()}

                    def _fresh_name(prefix: str) -> str:
                        # Keep SPICE element prefix letter; create a reasonably short deterministic suffix
                        # from the seeded RNG.
                        for _ in range(200):
                            cand = f"{prefix}{rnd.randrange(1, 10**9)}"
                            if cand not in all_existing and cand not in mapping.values():
                                return cand
                        # Fallback (should never happen)
                        return f"{prefix}{seed}"

                    for pref, ids in ids_by_pref.items():
                        if not ids:
                            continue
                        # Rename every instance to a fresh unique name (never equal to old).
                        for old in ids:
                            mapping[old] = _fresh_name(pref)

                    if not mapping:
                        return netlist, {}

                    # Rewrite first tokens
                    out_lines: list[str] = []
                    for ln in lines:
                        if not ln.strip():
                            out_lines.append(ln)
                            continue
                        parts = ln.split()
                        if not parts:
                            out_lines.append(ln)
                            continue
                        old_id = parts[0]
                        new_id = mapping.get(old_id)
                        if not new_id:
                            out_lines.append(ln)
                            continue
                        leading = ln[: len(ln) - len(ln.lstrip())]
                        out_lines.append(leading + " ".join([new_id] + parts[1:]))

                    return "\n".join(out_lines) + ("\n" if netlist.endswith("\n") else ""), mapping

                meta_seed = _get_meta_seed()
                # IMPORTANT: include run_id so renaming changes from run to run (user request).
                # run_id is the timestamped run directory name, e.g. run_20251215_014050
                shuf_seed = int.from_bytes(
                    hashlib.sha256(f"{run_id}:{meta_seed}:{Path(it.item_dir).name}:{q.id}:mc_shuf_ids".encode()).digest()[:8],
                    "big",
                )
                # Always rename/shuffle MOSFET instance names. Also rename R/C instance names for MCQs,
                # but DO NOT do so for analysis/feedback where choices explicitly use R1/R2/C1 notation.
                is_feedback_analysis = "data/dev/analysis/feedback" in str(item_dir).replace("\\", "/")
                # For analysis/filters, also rename inductors (L*) so TF questions can't be memorized via L1 etc.
                prefixes = ("M",) if is_feedback_analysis else ("M", "R", "C", "L")
                shuffled_text, id_map = _shuffle_instance_names(artifact_used, shuf_seed, prefixes=prefixes)
                if id_map:
                    mc_instance_rename_map = id_map
                    # Write a derived artifact next to the item for transparency/debugging
                    # IMPORTANT: this must be per-question. Otherwise multiple questions within the same
                    # item overwrite the same file, and the report ends up showing an artifact that
                    # doesn't match the prompt's substituted IDs.
                    safe_qid = "".join(ch if (ch.isalnum() or ch in {"_", "-", "."}) else "_" for ch in str(q.id))
                    shuf_path = item_dir / f"netlist_mc_shuffled_{safe_qid}.sp"
                    try:
                        shuf_path.write_text(shuffled_text, encoding="utf-8")
                        art_path = shuf_path
                    except Exception:
                        # If write fails, still use the shuffled text in-memory
                        pass
                    artifact_used = shuffled_text
                    # Also update inventory IDs shown to the model to match renamed transistors
                    inv_ids = [id_map.get(x, x) for x in inv_ids]
                    rand_info = {"source": "template", "mc_shuffled_ids": True, "seed": shuf_seed}

            # For non-analysis tracks, randomize SPICE netlist ordering to reduce memorization.
            if str(q.track).lower() != "analysis" and q.modality == "spice_netlist" and artifact_used:
                meta_seed = _get_meta_seed()
                per_item_seed = int.from_bytes(
                    hashlib.sha256(f"{meta_seed}:{Path(it.item_dir).name}:{q.id}".encode()).digest()[:8],
                    'big',
                )
                artifact_used = randomize_spice(artifact_used, per_item_seed)
                rand_info = {"seed": per_item_seed}

            # If MC choices were deferred, render them now so any {IN}/{OUTN}/{OUTP} placeholders
            # can be replaced using the final (possibly shuffled) SPICE netlist.
            if prompt_variant == "multiple_choice" and mc_answer_key and mc_choices_token in prompt:
                def _parse_mos(netlist: str) -> List[Dict[str, str]]:
                    mos: List[Dict[str, str]] = []
                    for raw in (netlist or "").splitlines():
                        s = raw.strip()
                        if not s or s.startswith(("*", ";", "//")):
                            continue
                        if not s[:1].upper().startswith("M"):
                            continue
                        parts = s.split()
                        if len(parts) < 6:
                            continue
                        mid, d, g, src, b, model = parts[:6]
                        mos.append({"id": mid, "d": d, "g": g, "s": src, "b": b, "model": model.lower()})
                    return mos

                def _is_supply(net: str) -> bool:
                    n = (net or "").lower()
                    return n in {"0", "gnd", "vss"} or n == "vdd" or n.startswith("vdd")

                def _role_candidates(netlist: str) -> Dict[str, List[str]]:
                    """Return candidate device IDs for IN/OUTN/OUTP to avoid post-substitution duplicates."""
                    mos = _parse_mos(netlist)
                    default_id = mos[0]["id"] if mos else "M1"
                    input_gate_nets = {
                        "vinp", "vinn", "vip", "vin", "inp", "inn", "in_p", "in_n", "in", "in+", "in-",
                    }
                    in_cands = [m["id"] for m in mos if (m.get("g") or "").lower() in input_gate_nets]
                    if not in_cands and mos:
                        in_cands = [mos[0]["id"]]
                    in_set = set(in_cands)

                    # Guess output node. Prefer explicit naming (vout/out*) over heuristics.
                    bad = set(input_gate_nets) | {"vbias", "vbias_n", "vbiasp", "vbiasn", "bias", "ntail", "tail"}
                    nets: List[str] = []
                    for m in mos:
                        for k in ("d", "s"):
                            nn = (m.get(k) or "").strip()
                            if not nn:
                                continue
                            nlow = nn.lower()
                            if _is_supply(nn) or nlow in bad or "bias" in nlow:
                                continue
                            nets.append(nn)
                    out_node = ""
                    # Strong preference for canonical output net names
                    for pref in ("vout", "voutp", "voutn", "vop", "von", "outp", "outn", "out"):
                        for nn in nets:
                            nlow = nn.lower()
                            if nlow == pref or nlow.startswith(pref):
                                out_node = nn
                                break
                        if out_node:
                            break
                    if not out_node:
                        counts: Dict[str, int] = {}
                        for nn in nets:
                            counts[nn] = counts.get(nn, 0) + 1
                        out_node = max(counts.items(), key=lambda kv: kv[1])[0] if counts else ""

                    # Support both Sky130-ish model names (nfet/pfet) and generic NMOS/PMOS.
                    nmos = [
                        m for m in mos
                        if ("nch" in m["model"]) or ("nfet" in m["model"]) or ("nmos" in m["model"])
                    ]
                    pmos = [
                        m for m in mos
                        if ("pch" in m["model"]) or ("pfet" in m["model"]) or ("pmos" in m["model"])
                    ]
                    # If a circuit is single-polarity in the template (e.g. generic NMOS-only toy netlists),
                    # fall back to the available devices rather than collapsing to a single ID.
                    if not nmos and pmos:
                        nmos = pmos
                    if not pmos and nmos:
                        pmos = nmos

                    # Output-connected devices (drain OR source tied to output node).
                    # IMPORTANT: exclude the input pair devices from OUTN/OUTP candidates.
                    # Otherwise, for single-ended OTAs where one input device drain is vout,
                    # distractors like gm_{OUTN}/CL can become equally-correct gm_{IN}/CL.
                    out_connected = [
                        m for m in mos
                        if out_node
                        and (m.get("d") == out_node or m.get("s") == out_node)
                        and (m.get("id") not in in_set)
                    ]
                    nmos_out = [
                        m for m in nmos
                        if out_node
                        and (m.get("d") == out_node or m.get("s") == out_node)
                        and (m.get("id") not in in_set)
                    ]
                    pmos_out = [
                        m for m in pmos
                        if out_node
                        and (m.get("d") == out_node or m.get("s") == out_node)
                        and (m.get("id") not in in_set)
                    ]

                    # Candidate ordering: keep OUTN/OUTP polarity-pure.
                    # Mixing polarities here can collapse OUTN and OUTP to the same single device in
                    # small OTAs (e.g. only PMOS tied to vout besides the input device).
                    outn_cands = [m["id"] for m in nmos_out]
                    outp_cands = [m["id"] for m in pmos_out]
                    if not outn_cands:
                        # Fall back to any NMOS device, but never pick input-pair devices.
                        outn_cands = [m["id"] for m in nmos if m.get("id") not in in_set]
                        if not outn_cands:
                            outn_cands = [m["id"] for m in mos if m.get("id") not in in_set]
                    if not outp_cands:
                        # Fall back to any PMOS device, but never pick input-pair devices.
                        outp_cands = [m["id"] for m in pmos if m.get("id") not in in_set]
                        if not outp_cands:
                            outp_cands = [m["id"] for m in mos if m.get("id") not in in_set]
                    if not outn_cands:
                        outn_cands = [m["id"] for m in mos]
                    if not outp_cands:
                        outp_cands = [m["id"] for m in mos]
                    # Cap to a few to keep combinatorics small
                    # Also provide a pool of "other" devices for distractors that intentionally use
                    # the wrong transistor's parameters (e.g., gm_{X1} instead of gm_{IN}).
                    other_pool = [m["id"] for m in mos if m.get("id") and (m.get("id") not in in_set)]

                    # Swing-specific: pick device stacks from output to rails to support Vov subscripts
                    # that correspond to the correct transistors in the netlist.
                    def _is_ground(net: str) -> bool:
                        n = (net or "").lower()
                        return n in {"0", "gnd", "vss"}

                    def _find_supply_node() -> str:
                        # Prefer canonical VDD net if present in the netlist.
                        nets_seen: List[str] = []
                        for m in mos:
                            for k in ("d", "g", "s", "b"):
                                nn = (m.get(k) or "").strip()
                                if nn:
                                    nets_seen.append(nn)
                        for nn in nets_seen:
                            if nn.lower() == "vdd":
                                return nn
                        for nn in nets_seen:
                            if nn.lower().startswith("vdd"):
                                return nn
                        return "VDD"

                    vdd_node = _find_supply_node()

                    def _build_adj(pol: str) -> Dict[str, List[tuple[str, str]]]:
                        adj: Dict[str, List[tuple[str, str]]] = {}
                        for m in mos:
                            mid = m.get("id") or ""
                            if not mid:
                                continue
                            model = (m.get("model") or "").lower()
                            is_n = ("nch" in model) or ("nfet" in model) or ("nmos" in model)
                            is_p = ("pch" in model) or ("pfet" in model) or ("pmos" in model)
                            if pol == "n" and not is_n:
                                continue
                            if pol == "p" and not is_p:
                                continue
                            a = (m.get("d") or "").strip()
                            b = (m.get("s") or "").strip()
                            if not a or not b:
                                continue
                            adj.setdefault(a, []).append((b, mid))
                            adj.setdefault(b, []).append((a, mid))
                        return adj

                    def _shortest_dev_path(adj: Dict[str, List[tuple[str, str]]], start: str, targets: set[str], max_devs: int) -> List[str]:
                        from collections import deque
                        # BFS on nodes, tracking device path
                        q = deque()
                        q.append((start, []))
                        seen: set[tuple[str, int]] = {(start, 0)}
                        best: List[str] | None = None
                        while q:
                            node, dpath = q.popleft()
                            if node in targets:
                                if best is None or len(dpath) < len(best) or (len(dpath) == len(best) and tuple(dpath) < tuple(best)):
                                    best = dpath
                                continue
                            if len(dpath) >= max_devs:
                                continue
                            for nxt, did in adj.get(node, []):
                                st = (nxt, len(dpath) + 1)
                                if st in seen:
                                    continue
                                seen.add(st)
                                q.append((nxt, dpath + [did]))
                        return best or []

                    n_adj = _build_adj("n")
                    p_adj = _build_adj("p")
                    n_path = _shortest_dev_path(n_adj, out_node, targets={"0", "gnd", "vss"}, max_devs=3) if out_node else []
                    p_path = _shortest_dev_path(p_adj, out_node, targets={vdd_node, "vdd", "VDD"}, max_devs=2) if out_node else []

                    swing_roles: Dict[str, List[str]] = {}
                    if n_path:
                        swing_roles["N1"] = [n_path[0]]
                    if len(n_path) > 1:
                        swing_roles["N2"] = [n_path[1]]
                    if len(n_path) > 2:
                        swing_roles["N3"] = [n_path[2]]
                    if p_path:
                        swing_roles["P1"] = [p_path[0]]
                    if len(p_path) > 1:
                        swing_roles["P2"] = [p_path[1]]

                    return {
                        "IN": in_cands[:4] if in_cands else [default_id],
                        "OUTN": outn_cands[:4] if outn_cands else [default_id],
                        "OUTP": outp_cands[:4] if outp_cands else [default_id],
                        "X": other_pool[:12] if other_pool else [default_id],
                        **swing_roles,
                    }

                def _pick_role_map(netlist: str, mc_choices: Dict[str, str]) -> Dict[str, str]:
                    cands = _role_candidates(netlist)

                    def _subst(text: str, rm: Dict[str, str]) -> str:
                        for k, v in rm.items():
                            text = text.replace("{" + k + "}", v)
                        return text

                    def _norm(s: str) -> str:
                        return s.lower().replace(" ", "")

                    # Try combinations; maximize distinct IDs first, but accept fewer if it yields unique rendered choices.
                    combos = []
                    for in_id in cands["IN"]:
                        for outn_id in cands["OUTN"]:
                            for outp_id in cands["OUTP"]:
                                combos.append((len({in_id, outn_id, outp_id}), in_id, outn_id, outp_id))
                    combos.sort(key=lambda t: (-t[0], t[1], t[2], t[3]))

                    for _, in_id, outn_id, outp_id in combos:
                        # Prefer distinct role IDs when possible; avoids duplicate-choice issues like
                        # gm_{OUTN}/Cload == gm_{OUTP}/Cload.
                        if outn_id == outp_id:
                            continue
                        rm = {"IN": in_id, "OUTN": outn_id, "OUTP": outp_id}
                        rendered = [_norm(_subst(str(mc_choices[k]), rm)) for k in sorted(mc_choices.keys())]
                        if len(set(rendered)) == len(rendered):
                            return rm

                    # As a last resort, prefer IN != OUTN if possible (helps many formula-style MCQs).
                    for _, in_id, outn_id, outp_id in combos:
                        if in_id != outn_id:
                            # Also try to pick OUTP distinct from OUTN when possible
                            outp = outp_id
                            if outp == outn_id:
                                for cand_outp in cands.get("OUTP", []) or []:
                                    if cand_outp != outn_id:
                                        outp = cand_outp
                                        break
                            return {"IN": in_id, "OUTN": outn_id, "OUTP": outp}
                    # Final fallback: pick firsts but enforce OUTP != OUTN if possible
                    in0 = cands["IN"][0]
                    outn0 = cands["OUTN"][0]
                    outp0 = cands["OUTP"][0]
                    if outp0 == outn0:
                        for cand_outp in cands.get("OUTP", []) or []:
                            if cand_outp != outn0:
                                outp0 = cand_outp
                                break
                    return {"IN": in0, "OUTN": outn0, "OUTP": outp0}

                role_map: Dict[str, str] = {}
                if q.modality == "spice_netlist" and artifact_used:
                    def _needed_keys(mc_choices: Dict[str, str]) -> set[str]:
                        blob = " ".join(str(v) for v in (mc_choices or {}).values())
                        needed = set()
                        for k in ("IN", "OUTN", "OUTP", "X1", "X2", "X3", "N1", "N2", "N3", "P1", "P2"):
                            if "{" + k + "}" in blob:
                                needed.add(k)
                        return needed

                    def _pick_role_map_all(netlist: str, mc_choices: Dict[str, str]) -> Dict[str, str]:
                        """
                        Pick role IDs (IN/OUTN/OUTP and optional X1/X2/X3) such that rendered MC choices
                        are unique. This prevents duplicate options and “multiple correct” cases that
                        arise when symmetric devices are used in distractors.
                        """
                        needed = _needed_keys(mc_choices)
                        cands = _role_candidates(netlist)

                        def _subst(text: str, rm: Dict[str, str]) -> str:
                            for k, v in rm.items():
                                text = text.replace("{" + k + "}", v)
                            return text

                        def _norm(s: str) -> str:
                            return s.lower().replace(" ", "")

                        # Never use literal "M1" as a fallback (might not exist after renaming).
                        # Prefer any available candidate from the netlist-derived pools.
                        any_id = (cands.get("IN") or cands.get("OUTN") or cands.get("OUTP") or cands.get("X") or ["M1"])[0]
                        in_list = list(cands.get("IN", []) or [any_id])
                        outn_list = list(cands.get("OUTN", []) or [any_id])
                        outp_list = list(cands.get("OUTP", []) or [any_id])
                        x_list = list(cands.get("X", []) or [any_id])

                        # Keep search small/deterministic
                        in_list = in_list[:4]
                        outn_list = outn_list[:4]
                        outp_list = outp_list[:4]
                        x_list = x_list[:10]

                        # Search combos; require OUTN != OUTP when both are needed
                        for in_id in in_list:
                            for outn_id in outn_list:
                                for outp_id in outp_list:
                                    if "OUTN" in needed and "OUTP" in needed and outn_id == outp_id:
                                        continue
                                    rm_base = {"IN": in_id, "OUTN": outn_id, "OUTP": outp_id}
                                    # Fixed swing roles from netlist-derived stacks (if needed)
                                    for k in ("N1", "N2", "N3", "P1", "P2"):
                                        if k in needed:
                                            vals = cands.get(k, [])
                                            if vals:
                                                rm_base[k] = vals[0]
                                    # Choose extra roles if needed
                                    used = set(rm_base.values()) | set(in_list)  # exclude other input-pair devices too
                                    extras_pool = [x for x in x_list if x not in used]
                                    # Build candidate assignments for X roles
                                    x_assignments = [({},)]  # type: ignore
                                    if any(k in needed for k in ("X1", "X2", "X3")):
                                        # Greedy permutations
                                        xs = extras_pool[:6] if extras_pool else x_list[:6]
                                        perms = []
                                        for a in xs:
                                            for b in xs:
                                                if b == a:
                                                    continue
                                                for c in xs:
                                                    if c in {a, b}:
                                                        continue
                                                    perms.append({"X1": a, "X2": b, "X3": c})
                                        x_assignments = perms or [{"X1": xs[0] if xs else "M1", "X2": xs[1] if len(xs) > 1 else "M1", "X3": xs[2] if len(xs) > 2 else "M1"}]

                                    for xa in x_assignments:
                                        rm = dict(rm_base)
                                        # Only include keys that are needed (keeps substitution stable)
                                        for k in ("X1", "X2", "X3"):
                                            if k in needed:
                                                rm[k] = xa.get(k, rm_base.get("OUTN", "M1"))
                                        rendered = [_norm(_subst(str(mc_choices[k]), rm)) for k in sorted(mc_choices.keys())]
                                        if len(set(rendered)) == len(rendered):
                                            # Return only needed keys (plus IN/OUTN/OUTP for compatibility)
                                            out = {k: rm[k] for k in ("IN", "OUTN", "OUTP", "N1", "N2", "N3", "P1", "P2") if k in rm}
                                            for k in ("X1", "X2", "X3"):
                                                if k in needed:
                                                    out[k] = rm[k]
                                            return out

                        # Fallback: preserve legacy selection, but ALWAYS fill any needed X roles
                        # so placeholders never leak into the rendered prompt.
                        base = _pick_role_map(netlist, mc_choices)
                        if not base:
                            base = {"IN": in_list[0], "OUTN": outn_list[0], "OUTP": outp_list[0]}

                        # Ensure OUTP != OUTN when both are needed (best effort)
                        if "OUTN" in needed and "OUTP" in needed and base.get("OUTN") == base.get("OUTP"):
                            for cand_outp in outp_list:
                                if cand_outp != base.get("OUTN"):
                                    base["OUTP"] = cand_outp
                                    break

                        if any(k in needed for k in ("X1", "X2", "X3")):
                            used = set(base.values()) | set(in_list)
                            pool = [x for x in x_list if x not in used] or [x for x in x_list if x not in set(base.values())] or x_list
                            # deterministic pick
                            picks = []
                            for x in pool:
                                if x not in picks:
                                    picks.append(x)
                                if len(picks) >= 3:
                                    break
                            while len(picks) < 3:
                                picks.append(pool[0] if pool else base.get("OUTN", any_id))
                            if "X1" in needed:
                                base["X1"] = picks[0]
                            if "X2" in needed:
                                base["X2"] = picks[1]
                            if "X3" in needed:
                                base["X3"] = picks[2]

                        # As a last guard: if this fallback still yields duplicates, strip OUTP (when unused)
                        # and keep mapping minimal.
                        return base

                    try:
                        role_map = _pick_role_map_all(artifact_used, mc_answer_key.get("choices", {}))
                    except Exception:
                        role_map = {}

                def _subst_placeholders(s: str) -> str:
                    if not s:
                        return s
                    for k, v in (role_map or {}).items():
                        s = s.replace("{" + k + "}", v)
                    return s

                def _apply_instance_renames(s: str) -> str:
                    """Replace any literal instance IDs in choices with their renamed IDs."""
                    if not s or not mc_instance_rename_map:
                        return s
                    import re
                    # Use conservative boundaries: SPICE IDs are typically [A-Za-z0-9_]+
                    for old, new in mc_instance_rename_map.items():
                        if old == new:
                            continue
                        pat = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])")
                        s = pat.sub(new, s)
                    return s

                choice_lines: List[str] = []
                rendered_choices: Dict[str, str] = {}
                for letter in sorted(mc_answer_key.get("choices", {}).keys()):
                    choice_text = str(mc_answer_key["choices"][letter])
                    choice_text = _subst_placeholders(choice_text)
                    choice_text = _apply_instance_renames(choice_text)
                    rendered_choices[letter] = choice_text

                # Final guard: ensure MC choices are unique after substitution/renaming.
                # This prevents "multiple correct answers" caused by symmetric devices (e.g. input pair)
                # or tiny netlists with too few distinct devices for OUTN/OUTP/X roles.
                correct_letter = str(mc_answer_key.get("correct_answer", "")).strip().upper()
                def _norm_choice(s: str) -> str:
                    return (s or "").lower().replace(" ", "")

                def _gbw_fallbacks(correct: str) -> List[str]:
                    # Extract gm_* and capacitor token (C*) from the correct option.
                    import re
                    gm = None
                    cap = None
                    m = re.search(r"(gm_[A-Za-z0-9_]+)", correct)
                    if m:
                        gm = m.group(1)
                    m = re.search(r"/(C[A-Za-z0-9_]+)", correct)
                    if m:
                        cap = m.group(1)
                    if not gm or not cap:
                        return []
                    return [
                        f"GBW ≈ {gm}/(2·{cap})",
                        f"GBW ≈ ( {gm} )²/{cap}".replace(" ( ", "(").replace(" )", ")"),
                        f"GBW ≈ {cap}/{gm}",
                        f"GBW ≈ {gm}·{cap}",
                        f"GBW ≈ {gm}/(2π{cap})",
                        f"GBW ≈ {gm}/(3·{cap})",
                        f"GBW ≈ {gm}/{cap}²",
                    ]

                def _gain_dc_fallbacks(correct: str) -> List[str]:
                    import re
                    gm = None
                    ro = None
                    m = re.search(r"(gm_[A-Za-z0-9_]+)", correct)
                    if m:
                        gm = m.group(1)
                    m = re.search(r"(ro_[A-Za-z0-9_]+)", correct)
                    if m:
                        ro = m.group(1)
                    if not gm or not ro:
                        return []
                    return [
                        f"DC gain A0 ≈ {gm}·{ro}",
                        f"DC gain A0 ≈ {gm}·{ro}/4",
                        f"DC gain A0 ≈ 2·{gm}·{ro}",
                        f"DC gain A0 ≈ {gm}/{ro}",
                        f"DC gain A0 ≈ ({gm}·{ro})²/2",
                    ]

                def _noise_fallbacks(correct: str) -> List[str]:
                    import re
                    gm = None
                    m = re.search(r"(gm_[A-Za-z0-9_]+)", correct)
                    if m:
                        gm = m.group(1)
                    if not gm:
                        return []
                    return [
                        f"Vn,out² ≈ 16kT/(3{gm})",
                        f"Vn,out² ≈ 8kT/(3{gm})",  # canonical
                        f"Vn,out² ≈ 8kT/({gm})",
                        f"Vn,out² ≈ 8kT·{gm}",
                        f"Vn,out² ≈ 8kT/(3{gm}²)",
                    ]

                def _rout_fallbacks(correct: str) -> List[str]:
                    import re
                    ro = None
                    m = re.search(r"(ro_[A-Za-z0-9_]+)", correct)
                    if m:
                        ro = m.group(1)
                    if not ro:
                        return []
                    return [
                        f"rout ≈ {ro}/2",
                        f"rout ≈ 2·{ro}",
                        f"rout ≈ {ro} + {ro}",
                        f"rout ≈ {ro}·{ro}",
                        f"rout ≈ √({ro})",
                    ]

                aspect = str((q.meta or {}).get("aspect") or "").strip()
                correct_text = rendered_choices.get(correct_letter, "")
                if aspect == "gbw":
                    pool = _gbw_fallbacks(correct_text)
                elif aspect == "gain_dc":
                    pool = _gain_dc_fallbacks(correct_text)
                elif aspect == "noise_white":
                    pool = _noise_fallbacks(correct_text)
                elif aspect == "rout":
                    pool = _rout_fallbacks(correct_text)
                else:
                    pool = []

                # Expand fallback pools to reliably break duplicates even when many common forms are already present.
                # (These extra variants remain plausible "wrong math" distractors.)
                if aspect == "gbw" and correct_text:
                    pool = pool + [
                        pool[0].replace("/(2·", "/(4·") if pool else "",
                        pool[0].replace("/(2·", "/(8·") if pool else "",
                    ]
                elif aspect == "gain_dc" and correct_text:
                    pool = pool + [
                        "DC gain A0 ≈ " + correct_text.split("≈", 1)[-1].strip().replace("/2", "/8"),
                        "DC gain A0 ≈ " + correct_text.split("≈", 1)[-1].strip().replace("/2", "/16"),
                        "DC gain A0 ≈ √(" + correct_text.split("≈", 1)[-1].strip().replace("/2", "") + ")",
                    ]
                elif aspect == "noise_white" and correct_text:
                    # Introduce more constant-factor variants using the same gm token.
                    pool = pool + [
                        correct_text.replace("8kT/(3", "4kT/(3"),
                        correct_text.replace("8kT/(3", "32kT/(3"),
                        correct_text.replace("8kT/(3", "8kT/(6"),
                    ]
                elif aspect == "rout" and correct_text:
                    pool = pool + [
                        correct_text.replace("rout ≈", "rout ≈ 3·"),
                    ]

                # Deterministically enforce uniqueness: walk choices and replace duplicates with fresh pool entries.
                letters = sorted(rendered_choices.keys())
                norms: Dict[str, str] = {}

                def _pick_replacement(used_norms: set[str]) -> str | None:
                    for cand in pool:
                        cn = _norm_choice(cand)
                        if not cn:
                            continue
                        if cn in used_norms:
                            continue
                        if correct_text and cn == _norm_choice(correct_text):
                            continue
                        return cand
                    return None

                # First pass: if the correct choice collides with another, we will replace the other.
                for letter in letters:
                    t = rendered_choices[letter]
                    n = _norm_choice(t)
                    if n and n not in norms:
                        norms[n] = letter

                # Second pass: replace duplicates (never modify correct choice text)
                used_norms = set(norms.keys())
                for letter in letters:
                    t = rendered_choices[letter]
                    n = _norm_choice(t)
                    first = norms.get(n)
                    if not n or first is None:
                        continue
                    if first == letter:
                        continue
                    # If current is correct, replace the earlier duplicate (if allowed).
                    if letter == correct_letter and first != correct_letter:
                        repl = _pick_replacement(used_norms)
                        if repl:
                            rendered_choices[first] = repl
                            used_norms.add(_norm_choice(repl))
                        continue
                    # Otherwise, replace current if it's not correct.
                    if letter != correct_letter:
                        repl = _pick_replacement(used_norms)
                        if repl:
                            rendered_choices[letter] = repl
                            used_norms.add(_norm_choice(repl))

                for letter in sorted(rendered_choices.keys()):
                    choice_lines.append(f"{letter}. {rendered_choices[letter]}")
                prompt = prompt.replace(mc_choices_token, "\n".join(choice_lines))

            # Predict
            error_msg: str | None = None
            pred_timer = perf_counter() if profiling.is_enabled() else None
            try:
                pred = adapter.predict([
                    {
                        "prompt": prompt,
                        "artifact_path": str(art_path),
                        "artifact": artifact_used,
                        "inventory_ids": inv_ids,
                        "question": q.model_dump(),
                        "attachments": attachment_paths,
                        "item_dir": str(item_dir),
                    }
                ])[0]
            except Exception as e:
                pred = ""
                error_msg = str(getattr(e, "message", e)) or str(e)
                # Print error to stderr so it's visible to the user - CRITICAL: never fail silently
                print(f"[ERROR] Prediction failed for {Path(it.item_dir).name}/{q.id}: {error_msg}", file=sys.stderr, flush=True)
                print(f"[ERROR] Full traceback:", file=sys.stderr, flush=True)
                traceback.print_exc(file=sys.stderr)
            finally:
                if profiling.is_enabled() and pred_timer is not None:
                    elapsed_ms = (perf_counter() - pred_timer) * 1000
                    profiling.log("adapter", "predict", elapsed_ms, context=f"model={slug}")

            # Skip judge if no judge_prompt and verification is enabled (verification-only mode)
            skip_judge = False
            if not q.judge_prompt:
                if q.verification and q.verification.get("enabled"):
                    skip_judge = True
                else:
                    raise SystemExit(f"Question {q.id} must specify judge_prompt relative to item_dir: {item_dir}")
            
            # Judge prompt (Markdown) and variables
            if not skip_judge:
                jpath = (item_dir / q.judge_prompt)
                if not jpath.exists():
                    alt = (item_dir.parent / "judge_prompts" / Path(q.judge_prompt).name)
                    if alt.exists():
                        jpath = alt
                    else:
                        raise SystemExit(f"Judge prompt not found for {q.id}: {jpath}")
                rubric_md = jpath.read_text(encoding='utf-8')
            else:
                rubric_md = None
                jpath = None
            # Build an effective inventory depending on modality
            def _inventory_from_casir(text: str) -> Inventory:
                try:
                    data = json.loads(_strip_json_comments(text))
                except Exception:
                    return it.inventory
                elems: Dict[str, Any] = {}
                nets: List[str] = []
                for n in data.get("nets", []) or []:
                    if isinstance(n, dict):
                        nid = str(n.get("id", "")).strip()
                    else:
                        nid = str(n).strip()
                    if nid:
                        nets.append(nid)
                try:
                    from .types import InventoryElement  # type: ignore
                except Exception:
                    from harness.types import InventoryElement  # type: ignore
                elements: Dict[str, InventoryElement] = {}
                cap_ids: List[str] = []
                for m in data.get("motifs", []) or []:
                    mid = str(m.get("id", "")).strip()
                    mtype = str(m.get("type", "motif")).strip()
                    ports = m.get("ports", {}) or {}
                    conns: List[str] = []
                    for v in ports.values():
                        if isinstance(v, str) and v.strip():
                            conns.append(v.strip())
                    aliases: List[str] = []
                    # Allow citing port role names (e.g., in, out, mid, bias, gnd)
                    try:
                        for pk in ports.keys():
                            pks = str(pk).strip()
                            if pks:
                                aliases.append(pks)
                    except Exception:
                        pass
                    if mtype.lower() in ("cap", "capacitor"):
                        cap_ids.append(mid)
                        aliases.extend(["Cload", "CL"])
                    elements[mid] = InventoryElement(type=mtype, nets=conns or None, aliases=aliases or None)
                try:
                    from .types import Inventory as Inv  # type: ignore
                except Exception:
                    from harness.types import Inventory as Inv  # type: ignore
                inv = Inv(elements=elements, nets=sorted(set(nets)))
                return inv

            eff_inv: Inventory = it.inventory
            if q.modality == "casIR":
                # Prefer artifact_used; for design track, fall back to template answer key
                src_text_for_inv = None
                if artifact_used:
                    src_text_for_inv = artifact_used
                else:
                    # Answer keys are loaded from YAML files (see rubric rendering below)
                    try:
                        mpath = item_dir / "meta.json"
                        if mpath.exists():
                            mm = json.loads(mpath.read_text(encoding='utf-8'))
                            tpath = mm.get("template_path") or mm.get("template")
                            if isinstance(tpath, str) and tpath.strip():
                                tdir = (item_dir / tpath).resolve()
                                keyp = tdir / "netlist.cir"
                                if keyp.exists():
                                    src_text_for_inv = keyp.read_text(encoding='utf-8')
                    except Exception:
                        src_text_for_inv = None
                if src_text_for_inv:
                    eff_inv = _inventory_from_casir(src_text_for_inv)
            elif q.modality == "cascode":
                try:
                    from .types import Inventory as Inv  # type: ignore
                except Exception:
                    from harness.types import Inventory as Inv  # type: ignore
                eff_inv = Inv(elements={}, nets=[], blocks={})

            # Render judge prompt with YAML variables under item_dir/rubrics/<stem>.yaml
            if not skip_judge:
                stem = Path(jpath).stem
                vars_yaml = item_dir / "rubrics" / f"{stem}.yaml"
                vars_map: Dict[str, Any] = {}

                # Build runtime_vars from bug_info for template rendering
                # Only emit runtime vars when a mutation actually occurred
                # If no mutation happened, runtime_vars will be empty
                runtime_vars = {k: str(v) for k, v in bug_info.items()} if bug_info else {}
                
                if vars_yaml.exists():
                    try:
                        # Render YAML as a template to allow includes and runtime vars
                        vars_yaml_text = vars_yaml.read_text(encoding='utf-8')
                        rendered_yaml = render_template(vars_yaml_text, runtime_vars, base_dir=vars_yaml.parent)
                        vars_map = yaml.safe_load(rendered_yaml) or {}
                    except Exception as e:
                        print(f"[yellow]Warning: Failed to render/parse {vars_yaml}: {e}[/yellow]")
                        vars_map = {}
                # unwrap namespaced
                if isinstance(vars_map, dict) and stem in vars_map and isinstance(vars_map[stem], dict):
                    vars_map = vars_map[stem]

                # Inject bug_info into vars_map for template rendering (debugging tasks)
                if bug_info:
                    vars_map.update({k: str(v) for k, v in bug_info.items()})
                    # Derive expected_type and actual_type from bug_info if not present
                    if "from_type" in bug_info and "expected_type" not in vars_map:
                        vars_map["expected_type"] = str(bug_info["from_type"])
                    if "to_type" in bug_info and "actual_type" not in vars_map:
                        vars_map["actual_type"] = str(bug_info["to_type"])

                # Merge runtime_vars and vars_map for judge prompt rendering
                all_vars = {**runtime_vars, **{k: str(v) for k, v in vars_map.items()}}

                # Note: For design tasks, answer keys are resolved via {modmux:answer_key} in templates
                # No need to manually inject answer_key variable anymore

                try:
                    rubric_md_rendered = render_template(rubric_md, all_vars, base_dir=jpath.parent, modality=q.modality)
                except Exception as e:
                    raise SystemExit(f"Failed to render judge prompt for {q.id} at {jpath}: {e}")

            # Define objective scoring function
            def _compute_objective_score(metrics: Dict[str, Any], design_spec: Dict[str, Any]) -> float:
                """
                Compute normalized objective score (0-1) based on how well metrics meet specifications.
                Uses percentage deviation from target/spec:
                - Score = 1.0 if spec is met
                - Score = max(0, 1 - |percentage_deviation|/100) if spec is not met
                
                Final score is equally-weighted average across all specs.
                """
                if not design_spec.get("specifications"):
                    return 0.0
                
                spec_scores = []
                
                for spec_name, spec_data in design_spec["specifications"].items():
                    # Map spec names to metric names
                    metric_map = {
                        "cutoff_frequency": "fc_low",
                        "dc_gain": "dc_gain_db",
                        "unity_gain_frequency": "unity_gain_freq_hz",
                        "gbw": "unity_gain_freq_hz",  # Map gbw to unity_gain_freq_hz
                        "phase_margin": "phase_margin_deg",
                        "power": "power_w",  # Power in Watts
                        "passband_gain": "passband_gain",
                        "stopband_attenuation": "stopband_gain",
                        "center_frequency": "center_frequency",
                        "quality_factor": "quality_factor",
                        "notch_frequency": "notch_freq",
                        "notch_depth": "notch_depth_db",
                        "characteristic_frequency": "fc_low",  # For all-pass filters
                        "phase_shift_at_f0": "phase_at_peak",  # Phase at characteristic frequency
                        "gain": "gain_vv",  # Linear gain (V/V)
                        "output_swing": "output_swing",
                        "input_common_mode_range": "input_cm_range",
                        "slew_rate": "slew_rate"
                    }
                    
                    metric_name = metric_map.get(spec_name, spec_name)
                    if metric_name not in metrics:
                        # If metric is missing, score as 0
                        spec_scores.append(0.0)
                        continue
                    
                    value = metrics[metric_name]
                    
                    # Special handling for attenuation specs (negative dB, lower/more negative is better)
                    is_attenuation = spec_name in ["stopband_attenuation", "notch_depth"]
                    
                    # Handle different spec types
                    # Note: "target" is aspirational; scoring is based on min/max boundaries
                    # For filters: "value" with "tolerance" defines acceptable range
                    if "value" in spec_data and "tolerance" in spec_data:
                        # Filter-style spec: value ± tolerance defines the acceptable range
                        target = spec_data["value"]
                        tolerance = spec_data["tolerance"]
                        min_val = target * (1 - tolerance)
                        max_val = target * (1 + tolerance)
                        
                        if min_val <= value <= max_val:
                            score = 1.0
                        else:
                            # Calculate % deviation from nearest boundary
                            if value < min_val:
                                reference = min_val
                            else:  # value > max_val
                                reference = max_val
                            
                            if reference == 0:
                                score = max(0.0, 1.0 - abs(value))
                            else:
                                pct_deviation = abs((value - reference) / reference) * 100
                                score = max(0.0, 1.0 - pct_deviation / 100)
                    elif "min" in spec_data and "max" in spec_data:
                        min_val = spec_data["min"]
                        max_val = spec_data["max"]
                        if min_val <= value <= max_val:
                            score = 1.0
                        else:
                            # Calculate % deviation from nearest boundary
                            if value < min_val:
                                reference = min_val
                            else:  # value > max_val
                                reference = max_val
                            
                            if reference == 0:
                                score = max(0.0, 1.0 - abs(value))
                            else:
                                pct_deviation = abs((value - reference) / reference) * 100
                                score = max(0.0, 1.0 - pct_deviation / 100)
                    elif "min" in spec_data:
                        min_val = spec_data["min"]
                        # For attenuation: more negative is better, so value <= min_val is good
                        # For normal specs: value >= min_val is good
                        if is_attenuation:
                            if value <= min_val:
                                score = 1.0
                            else:
                                # Failed: not negative enough
                                if min_val == 0:
                                    score = max(0.0, 1.0 - abs(value))
                                else:
                                    pct_deviation = abs((value - min_val) / min_val) * 100
                                    score = max(0.0, 1.0 - pct_deviation / 100)
                        else:
                            if value >= min_val:
                                score = 1.0
                            else:
                                # Failed: below minimum
                                if min_val == 0:
                                    score = max(0.0, 1.0 - abs(value))
                                else:
                                    pct_deviation = abs((value - min_val) / min_val) * 100
                                    score = max(0.0, 1.0 - pct_deviation / 100)
                    elif "max" in spec_data:
                        max_val = spec_data["max"]
                        if value <= max_val:
                            score = 1.0
                        else:
                            # Failed: above maximum
                            if max_val == 0:
                                score = max(0.0, 1.0 - abs(value))
                            else:
                                pct_deviation = abs((value - max_val) / max_val) * 100
                                score = max(0.0, 1.0 - pct_deviation / 100)
                    else:
                        # No spec criteria defined - skip this spec
                        continue
                    
                    # Clamp score to [0, 1] and add to list
                    score = max(0.0, min(1.0, score))
                    spec_scores.append(score)
                
                # Return equally-weighted average of all spec scores
                if spec_scores:
                    # Clamp final average to [0, 1]
                    return max(0.0, min(1.0, sum(spec_scores) / len(spec_scores)))
                else:
                    return 0.0

            # SPICE Verification (if enabled)
            verification_results = None
            if q.verification and q.verification.get("enabled"):
                try:
                    from harness.design_verification.spice_runner import SpiceRunner
                    from harness.design_verification.netlist_parser import parse_netlist_from_markdown
                    
                    # Load design spec
                    spec_file = item_dir / q.verification.get("spec_file", "verification/design_spec.json")
                    if spec_file.exists():
                        design_spec = json.loads(spec_file.read_text(encoding='utf-8'))
                        
                        # Parse netlist from LLM response
                        netlist = parse_netlist_from_markdown(pred)
                        
                        if netlist:
                            # Run SPICE simulation
                            pdk_path = Path("pdk/skywater130")
                            runner = SpiceRunner(pdk_path=pdk_path, work_dir=Path(f"outputs/temp_sim_{q.id}"))
                            sim_results = runner.run_simulation(netlist, design_spec, design_id=q.id)
                            
                            if sim_results.success:
                                # Compute derived metrics
                                # Phase margin from phase at UGF
                                # PM = 180° - |phase| (distance from -180° instability point)
                                if 'phase_at_ugf' in sim_results.metrics and 'phase_margin_deg' not in sim_results.metrics:
                                    phase = sim_results.metrics['phase_at_ugf']
                                    sim_results.metrics['phase_margin_deg'] = 180 - abs(phase)
                                
                                # Compute objective score based on specifications
                                objective_score = _compute_objective_score(sim_results.metrics, design_spec)
                                
                                # Store verification results (include design_spec for report)
                                verification_results = {
                                    "passed": True,
                                    "metrics": sim_results.metrics,
                                    "objective_score": objective_score,
                                    "design_spec": design_spec
                                }
                            else:
                                # Simulation failed
                                verification_results = {
                                    "passed": False,
                                    "error": sim_results.errors
                                }
                        else:
                            # No netlist found
                            verification_results = {
                                "passed": False,
                                "error": "No netlist found in response"
                            }
                except Exception as e:
                    # Exception during verification
                    verification_results = {
                        "passed": False,
                        "error": f"Verification exception: {str(e)}"
                    }

            # Judge
            judge = None
            # Multiple choice scoring: check if the answer matches correct letter
            mc_score = None
            if prompt_variant == "multiple_choice" and mc_answer_key:
                correct_letter = mc_answer_key.get("correct_answer", "").strip().upper()
                # Extract the model's answer (look for single letter A-J)
                import re
                # Look for patterns like "A", "Answer: A", "(A)", "The answer is A", etc.
                answer_pattern = r'\b([A-J])\b'
                matches = re.findall(answer_pattern, pred.upper())
                if matches:
                    model_answer = matches[0]  # Take first match
                    mc_correct = (model_answer == correct_letter)
                    mc_score = {
                        "correct": mc_correct,
                        "score": 1.0 if mc_correct else 0.0,
                        "model_answer": model_answer,
                        "correct_answer": correct_letter,
                        "answer_text": mc_answer_key.get("answer_text", "")
                    }
                else:
                    # No valid answer found
                    mc_score = {
                        "correct": False,
                        "score": 0.0,
                        "model_answer": None,
                        "correct_answer": correct_letter,
                        "answer_text": mc_answer_key.get("answer_text", ""),
                        "parse_error": "No valid answer letter (A-J) found in response"
                    }
            
            # Skip judge if verification is enabled (use objective score instead) or if MC scoring is used
            verification_enabled = q.verification and q.verification.get("enabled")
            if not skip_judge and not verification_enabled and not mc_score:
                try:
                    from .scoring.judge_anchored import judge_answer as judge_call  # type: ignore
                except Exception:
                    from harness.scoring.judge_anchored import judge_answer as judge_call  # type: ignore
                def _inventory_summary() -> Dict[str, Any]:
                    """Build a conservative inventory for groundedness/judging.

                    Only include actual IDs and nets from the item/template inventory.
                    Do NOT inject extra aliases/types (e.g., CL/Cload, cap/res/elem) or
                    ground synonyms into allowed_ids to avoid leaking hints or irrelevant tokens.
                    Provide common ground synonyms via canonical_map only, so judges can
                    accept them if models use them, without encouraging their use.
                    """
                    alias_map = eff_inv.alias_map()
                    # Only keys explicitly present in elements/blocks/nets
                    allowed = sorted(set(alias_map.keys()))
                    canonical_map = {k: v for k, v in alias_map.items() if k != v}

                    # Ground synonyms: offer mapping but do not add to allowed_ids
                    if any(n.strip().upper() == "0" or n.strip() == "0" for n in eff_inv.nets):
                        for syn in ("GND", "VSS"):
                            canonical_map.setdefault(syn, "0")

                    summary: Dict[str, Any] = {"allowed_ids": sorted(allowed), "canonical_map": canonical_map}
                    if q.modality == "cascode":
                        summary["grounding_disabled"] = True
                    return summary

                inv_summary = _inventory_summary()
                if args.judge_model == "dummy":
                    # Build a debug payload; keep concise, track-aware system prompt only
                    track_l = str(q.track or "").strip().lower()
                    if track_l == "design":
                        sys_prompt = (
                            "You are an impartial grading assistant for analog/mixed-signal circuit DESIGN. "
                            "You ONLY output JSON and never prose. Score the answer per rubric using the rubric and inventory."
                        )
                    elif track_l == "analysis":
                        sys_prompt = (
                            "You are an impartial grading assistant for analog/mixed-signal circuit ANALYSIS. "
                            "You ONLY output JSON and never prose. Score the answer per rubric using the rubric and inventory."
                        )
                    elif track_l == "debugging":
                        sys_prompt = (
                            "You are an impartial grading assistant for analog/mixed-signal circuit DEBUGGING. "
                            "You ONLY output JSON and never prose. Score the answer per rubric using the rubric and inventory."
                        )
                    else:
                        sys_prompt = (
                            "You are an impartial grading assistant for analog/mixed-signal design/analysis/debugging. "
                            "You ONLY output JSON and never prose. Score the answer per rubric using the rubric and inventory."
                        )
                    instr_flat = rubric_md_rendered
                    payload_dbg = {
                        "answer_to_evaluate": pred,
                        "inventory": inv_summary,
                    }
                    judge = {
                        "scores": {},
                        "overall": 0.0,
                        "debug": {
                            "system": sys_prompt,
                            "instructions": instr_flat,
                            "payload": payload_dbg,
                            "judge_model": "dummy",
                            "rubric_markdown": rubric_md_rendered,
                        },
                    }
                elif pred:
                    try:
                        judge = judge_call(pred, rubric_md_rendered, q.track, inv_summary, model=args.judge_model)
                    except Exception:
                        judge = None
                if judge and isinstance(judge.get("scores"), dict):
                    j_scores = judge["scores"]
                    if "overall" not in judge:
                        judge["overall"] = sum(j_scores.values())/len(j_scores) if j_scores else 0.0

            # Normalize family/topic labeling
            if "/" in str(args.split):
                parts = Path(str(args.split)).parts
                # Drop split head (e.g., 'dev') when present
                topic_str = "/".join(parts[1:]) if len(parts) > 1 else (parts[0] if parts else "")
            else:
                try:
                    rel = Path(it.item_dir).resolve().relative_to(split_dir.resolve())
                    parent = rel.parent
                    topic_str = parent.as_posix() if str(parent) != "." else Path(args.split).as_posix()
                except (ValueError, OSError):
                    topic_str = Path(it.item_dir).parent.name

            rec = {
                "model": slug,
                "item_id": item_dir.name,
                "family": topic_str,
                "topic": topic_str,
                "question_id": q.id,
                "track": q.track,
                "judge_id": q.judge_id if not skip_judge else None,
                "judge_prompt": str(jpath) if jpath else None,
                "modality": q.modality,
                "split": args.split,
                "aspect": (q.meta or {}).get("aspect"),
                "prompt_variant": prompt_variant,
                "prompt": prompt,
                "artifact_path": str(art_path),
                "artifact": artifact_used,
                "artifact_randomization": rand_info or None,
                "answer": pred,
                "judge": judge if not skip_judge else None,
                "mc_score": mc_score if mc_score else None,
            }
            
            # Add verification details if SPICE verification ran
            if q.verification and q.verification.get("enabled") and verification_results:
                rec["verification_details"] = {
                    "simulation_passed": verification_results.get("passed", False),
                    "metrics": verification_results.get("metrics", {}),
                    "objective_score": verification_results.get("objective_score"),
                    "error": verification_results.get("error") if not verification_results.get("passed") else None,
                    "design_spec": verification_results.get("design_spec")  # Include design_spec for report
                }
                # Also add top-level metrics for easy access in reports
                rec["verification_metrics"] = verification_results.get("metrics", {})
                if verification_results.get("objective_score") is not None:
                    rec["objective_score"] = verification_results.get("objective_score")
                if verification_results.get("error"):
                    rec["verification_errors"] = [verification_results.get("error")]
            
            if error_msg:
                rec["error"] = error_msg
            # No deterministic scoring; judge-only

            with write_lock:
                f_combined.write(json.dumps(rec) + "\n")
                model_files[slug].write(json.dumps(rec) + "\n")
                # Flush immediately to prevent data loss on crash
                f_combined.flush()
                model_files[slug].flush()
                total += 1
            with progress_lock:
                progress.update(task_id, advance=1)

            if profiling.is_enabled() and item_timer is not None:
                total_ms = (perf_counter() - item_timer) * 1000
                profiling.log("worker", "item_total", total_ms, context=f"item={Path(it.item_dir).name} question={q.id}")

        import time as _time
        item_timeout = float(os.getenv("EVAL_ITEM_TIMEOUT", "300.0"))  # 5 min per item default
        with ThreadPoolExecutor(max_workers=max(1, int(args.item_workers))) as item_pool:
            futs = []
            for it in items:
                for q in it.questions:
                    futs.append(item_pool.submit(process_q, it, q))
            for i, f in enumerate(futs):
                wait_start = perf_counter() if profiling.is_enabled() else None
                try:
                    # Add timeout to prevent indefinite hangs
                    f.result(timeout=item_timeout)
                except FutureTimeoutError:
                    print(f"[ERROR] Item {i+1}/{len(futs)} timed out after {item_timeout}s - continuing with remaining items", file=sys.stderr, flush=True)
                    # Write error record for timeout
                    try:
                        # Try to identify which item timed out (may not be perfect)
                        rec = {
                            "model": slug,
                            "error": f"Item processing timed out after {item_timeout}s",
                            "timeout": True,
                        }
                        with write_lock:
                            f_combined.write(json.dumps(rec) + "\n")
                            model_files[slug].write(json.dumps(rec) + "\n")
                            f_combined.flush()
                            model_files[slug].flush()
                    except Exception:
                        pass
                except Exception as e:
                    import traceback
                    print(f"[ERROR] Item {i+1}/{len(futs)} failed: {e}", file=sys.stderr, flush=True)
                    print(f"[ERROR] Full traceback:", file=sys.stderr, flush=True)
                    traceback.print_exc(file=sys.stderr)
                    # Continue processing other items
                    pass
                finally:
                    if profiling.is_enabled() and wait_start is not None:
                        wait_ms = (perf_counter() - wait_start) * 1000
                        if wait_ms > 100:
                            profiling.log(
                                "thread_pool",
                                "item_future_wait",
                                wait_ms,
                                context=f"model={slug} index={i+1}/{len(futs)}",
                            )

    with results_path.open("w") as f_combined:
        # Progress setup: one task per model
        with Progress(
            "{task.description}",
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            transient=False,
        ) as progress:
            model_tasks = {
                slug: progress.add_task(f"[green]{slug}[/green]", total=total_questions)
                for slug in model_slugs
            }

            max_workers = args.model_workers or len(model_slugs)
            model_timeout = float(os.getenv("EVAL_MODEL_TIMEOUT", "3600.0"))  # 1 hour per model default
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                futures = [ex.submit(run_for_model, slug) for slug in model_slugs]
                for i, f in enumerate(futures):
                    wait_start = perf_counter() if profiling.is_enabled() else None
                    try:
                        f.result(timeout=model_timeout)
                    except FutureTimeoutError:
                        print(f"[ERROR] Model {model_slugs[i]} timed out after {model_timeout}s", file=sys.stderr, flush=True)
                    except Exception as e:
                        print(f"[ERROR] Model {model_slugs[i]} failed: {e}", file=sys.stderr, flush=True)
                    finally:
                        if profiling.is_enabled() and wait_start is not None:
                            wait_ms = (perf_counter() - wait_start) * 1000
                            if wait_ms > 100:
                                profiling.log(
                                    "thread_pool",
                                    "model_future_wait",
                                    wait_ms,
                                    context=f"model={model_slugs[i]} index={i+1}/{len(futures)}",
                                )

    def _force_remove(path: Path) -> None:
        """Forcefully remove a file, directory, or symlink, handling broken symlinks and Windows quirks."""
        import os
        import shutil
        import subprocess
        import sys

        # Try multiple methods to remove the existing item
        removed = False
        try:
            if path.exists():
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                removed = True
        except OSError:
            # Broken symlink or access issue
            pass

        if not removed:
            try:
                # Try is_symlink without exists check
                if path.is_symlink():
                    path.unlink(missing_ok=True)
                    removed = True
            except OSError:
                pass

        if not removed:
            # Last resort: Windows-specific rmdir command for broken symlinks
            if sys.platform == 'win32':
                try:
                    subprocess.run(['rmdir', str(path)], shell=True, check=False, capture_output=True)
                    removed = True
                except:
                    pass
            else:
                try:
                    os.unlink(path)
                except (FileNotFoundError, OSError):
                    pass

    # Create/overwrite latest pointer
    latest = Path("outputs/latest")
    try:
        _force_remove(latest)
        # Use relative target to avoid nested 'outputs/outputs' paths
        latest.symlink_to(out_dir.name, target_is_directory=True)
    except Exception:
        # Windows without symlink perms or other issues: copy results
        import shutil
        _force_remove(latest)
        latest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(results_path, latest / "results.jsonl")
        (outputs_root / "latest_run.txt").write_text(str(out_dir), encoding='utf-8')
    # Ensure latest/results.jsonl is accessible; if not, copy it
    try:
        test_path = latest / "results.jsonl"
        if not test_path.exists():
            import shutil
            latest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(results_path, test_path)
    except Exception:
        pass

    # Close per-model files
    for fp in model_files.values():
        try:
            fp.close()
        except Exception:
            pass

    print(f"[green]Wrote {total} results to[/green] {results_path}")
    for slug in model_slugs:
        print(f"  per-model: {out_dir / slug / 'results.jsonl'}")

    # Auto-render human-readable report
    try:
        report_index = generate_report(results_path)
        # Also produce latest/report via symlinked latest dir
        print(f"[green]Rendered report:[/green] {report_index}")
    except SystemExit as e:
        print(f"[yellow]Report generation skipped:[/yellow] {e}")
    except Exception as e:
        print(f"[red]Report generation failed:[/red] {e}")
    # Update outputs index
    try:
        outputs_index = generate_outputs_index(outputs_root)
        print(f"[green]Updated outputs index:[/green] {outputs_index}")
    except Exception as e:
        print(f"[yellow]Outputs index update failed:[/yellow] {e}")

    if profiling.is_enabled():
        try:
            profile_log, profile_summary = profiling.write_reports(out_dir / "profiling")
            if profile_log:
                print(f"[green]Profiling log:[/green] {profile_log}")
            else:
                print("[yellow]Profiling enabled but no events were recorded.")
            if profile_summary:
                print(f"[green]Profiling summary:[/green] {profile_summary}")
        except Exception as e:
            print(f"[yellow]Profiling export failed:[/yellow] {e}")


if __name__ == "__main__":
    main()

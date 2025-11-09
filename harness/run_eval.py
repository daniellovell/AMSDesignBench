from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import math
import random
import yaml

from rich import print
from rich.progress import Progress, BarColumn, TimeElapsedColumn, TimeRemainingColumn, MofNCompleteColumn
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import threading

# Allow running as script or module
if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from harness.types import Inventory, Question, EvalItem  # type: ignore
    from harness.scoring.groundedness import groundedness  # type: ignore
    from harness.reporting.render import generate_report, generate_outputs_index  # type: ignore
    from harness.utils.template import render_template  # type: ignore
else:
    from .types import Inventory, Question, EvalItem
    from .scoring.groundedness import groundedness
    from .reporting.render import generate_report, generate_outputs_index
    from .utils.template import render_template


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
    Parse a model spec like "openai" or "openai:gpt-4o-mini" into (adapter, kwargs).
    For unknown adapters, everything after ':' is ignored.
    """
    if ":" in spec:
        name, rest = spec.split(":", 1)
        name = name.strip()
        rest = rest.strip()
        # For OpenAI, map to underlying model name
        if name == "openai" and rest:
            return name, {"model": rest}
        # For Anthropic, map to underlying model name
        if name == "anthropic" and rest:
            return name, {"model": rest}
        # For OpenRouter, pass model name through
        if name == "openrouter" and rest:
            return name, {"model": rest}
        # Future adapters can parse additional kv-pairs here
        return name, {}
    return spec.strip(), {}


def normalize_judge_model(spec: Optional[str]) -> Optional[str]:
    """
    Normalize judge model specs so we can reuse adapter-style strings
    (e.g., openai:gpt-4o-mini) while still passing raw model IDs to judge calls.
    """
    if spec is None:
        return None
    cleaned = str(spec).strip()
    if not cleaned:
        return None
    if ":" in cleaned:
        prefix, rest = cleaned.split(":", 1)
        if prefix.strip().lower() in {"openai", "anthropic", "openrouter"}:
            return rest.strip() or None
    return cleaned


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
        # Judge prompt defaults: map prompt_template stem to ../judge_prompts/<stem>.md
        if not qdict.get("judge_prompt"):
            try:
                stem = Path(str(qdict["prompt_template"]).strip()).stem
            except Exception:
                stem = "rubric"
            qdict["judge_prompt"] = (Path("../judge_prompts") / f"{stem}.md").as_posix()
        if not qdict.get("judge_id"):
            try:
                qdict["judge_id"] = Path(qdict["judge_prompt"]).stem
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
    ap.add_argument("--judge-model", "--judge_model", dest="judge_model", default=None, help="override judge model name")
    ap.add_argument("--model-workers", type=int, default=0, help="parallel model workers (0 = run all models in parallel)")
    ap.add_argument("--item-workers", type=int, default=8, help="per-model concurrent workers for items/questions")
    # Judge tuning
    ap.add_argument("--judge-rpm", type=float, default=None, help="Rate limit RPM for judge API (sets OPENAI_JUDGE_RPM)")
    ap.add_argument("--judge-tpm", type=float, default=None, help="Token per minute limit for judge API (sets OPENAI_JUDGE_TPM)")
    ap.add_argument("--judge-max-retries", type=int, default=None, help="Max retries for judge API (sets OPENAI_JUDGE_MAX_RETRIES)")
    ap.add_argument("--judge-concurrency", type=int, default=None, help="Max concurrent judge calls (sets OPENAI_JUDGE_CONCURRENCY)")
    args = ap.parse_args()
    # Judge is always enabled; no flag required

    # Apply judge tuning via environment for scorer module
    if args.judge_rpm is not None:
        os.environ["OPENAI_JUDGE_RPM"] = str(args.judge_rpm)
    if args.judge_tpm is not None:
        os.environ["OPENAI_JUDGE_TPM"] = str(args.judge_tpm)
    if args.judge_max_retries is not None:
        os.environ["OPENAI_JUDGE_MAX_RETRIES"] = str(args.judge_max_retries)
    if args.judge_concurrency is not None:
        os.environ["OPENAI_JUDGE_CONCURRENCY"] = str(args.judge_concurrency)

    # Load bench config (YAML)
    cfg = yaml.safe_load(Path("bench_config.yaml").read_text(encoding='utf-8')) or {}
    eval_cfg_raw = cfg.get("eval") or {}
    eval_cfg = eval_cfg_raw if isinstance(eval_cfg_raw, dict) else {}
    data_root = Path(cfg.get("paths", {}).get("data_root", "data"))
    # Prompts are referenced per-item: resolved as (item_dir/../prompts/<prompt_template>)
    outputs_root = Path(cfg.get("paths", {}).get("outputs_root", "outputs"))
    outputs_root.mkdir(parents=True, exist_ok=True)

    judge_model_cfg = eval_cfg.get("judge_model")
    judge_model_spec = args.judge_model if args.judge_model is not None else judge_model_cfg
    judge_model = normalize_judge_model(judge_model_spec)
    args.judge_model = judge_model

    split_dir = data_root / args.split
    if not split_dir.exists():
        raise SystemExit(f"Split not found: {split_dir}")

    # Resolve model list (support both --models and legacy --model). If none, try bench_config eval.models.
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
        if kwargs.get("model"):
            slug = f"{name}_{kwargs['model']}".replace("/", "-")
        else:
            slug = name
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
        task_id = model_tasks[slug]

        def process_q(it: EvalItem, q: Question):
            nonlocal total
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
                prompt = prompt_tmpl.format(modality=_display_modality(q.modality), examples=examples, design_brief=design_brief)
            except Exception:
                # Back-compat: older templates may not use {examples}
                try:
                    prompt = prompt_tmpl.format(modality=_display_modality(q.modality), design_brief=design_brief)
                except Exception:
                    prompt = prompt_tmpl.format(modality=_display_modality(q.modality))

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

            if q.modality == "spice_netlist" and artifact_used:
                meta_seed = _get_meta_seed()
                per_item_seed = int.from_bytes(
                    hashlib.sha256(f"{meta_seed}:{Path(it.item_dir).name}:{q.id}".encode()).digest()[:8],
                    'big',
                )
                artifact_used = randomize_spice(artifact_used, per_item_seed)
                rand_info = {"seed": per_item_seed}

            # Predict
            error_msg: str | None = None
            try:
                pred = adapter.predict([
                    {
                        "prompt": prompt,
                        "artifact_path": str(item_dir / q.artifact_path),
                        "artifact": artifact_used,
                        "inventory_ids": inv_ids,
                        "question": q.model_dump(),
                        "attachments": attachment_paths,
                    }
                ])[0]
            except Exception as e:
                pred = ""
                error_msg = str(getattr(e, "message", e))

            # Judge prompt (Markdown) and variables
            if not q.judge_prompt:
                raise SystemExit(f"Question {q.id} must specify judge_prompt relative to item_dir: {item_dir}")
            jpath = (item_dir / q.judge_prompt)
            if not jpath.exists():
                alt = (item_dir.parent / "judge_prompts" / Path(q.judge_prompt).name)
                if alt.exists():
                    jpath = alt
                else:
                    raise SystemExit(f"Judge prompt not found for {q.id}: {jpath}")
            rubric_md = jpath.read_text(encoding='utf-8')
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
                                
                                # Evaluate against specs and add to per_criterion scores
                                for c in rubric.criteria:
                                    if c.verification:
                                        metric_name = c.metric
                                        threshold = c.threshold
                                        comparison = c.comparison or ">="
                                        
                                        if metric_name in sim_results.metrics:
                                            value = sim_results.metrics[metric_name]
                                            passed = False
                                            if comparison == ">=":
                                                passed = value >= threshold
                                            elif comparison == "<=":
                                                passed = value <= threshold
                                            elif comparison == ">":
                                                passed = value > threshold
                                            elif comparison == "<":
                                                passed = value < threshold
                                            
                                            criterion_score = c.weight if passed else 0.0
                                            scores["per_criterion"][c.id] = {
                                                "score": criterion_score / max(c.weight, 1e-9),
                                                "value": value,
                                                "threshold": threshold,
                                                "passed": passed
                                            }
                                            scores["points"] += criterion_score
                                            scores["total_weight"] += c.weight
                                        else:
                                            scores["per_criterion"][c.id] = {
                                                "score": 0.0,
                                                "error": f"Metric '{metric_name}' not found in simulation results"
                                            }
                                            scores["total_weight"] += c.weight
                                
                                # Add overall verification summary
                                scores["verification"] = {
                                    "passed": sim_results.success,
                                    "metrics": sim_results.metrics
                                }
                                # Recalculate raw score with verification included
                                scores["raw"] = scores["points"] / max(scores["total_weight"], 1e-9)
                                scores["pass"] = scores["raw"] >= rubric.scoring.get("min_pass", 0.7)
                            else:
                                # Simulation failed - zero out all verification criteria
                                for c in rubric.criteria:
                                    if c.verification:
                                        scores["per_criterion"][c.id] = {
                                            "score": 0.0,
                                            "error": "Simulation failed"
                                        }
                                        scores["total_weight"] += c.weight
                                scores["verification"] = {
                                    "passed": False,
                                    "score": 0.0,
                                    "error": sim_results.errors
                                }
                                scores["raw"] = scores["points"] / max(scores["total_weight"], 1e-9)
                                scores["pass"] = scores["raw"] >= rubric.scoring.get("min_pass", 0.7)
                        else:
                            # No netlist found - zero out verification criteria
                            for c in rubric.criteria:
                                if c.verification:
                                    scores["per_criterion"][c.id] = {
                                        "score": 0.0,
                                        "error": "No netlist found in response"
                                    }
                                    scores["total_weight"] += c.weight
                            scores["raw"] = scores["points"] / max(scores["total_weight"], 1e-9)
                            scores["pass"] = scores["raw"] >= rubric.scoring.get("min_pass", 0.7)
                except Exception as e:
                    # Exception - zero out verification criteria
                    for c in rubric.criteria:
                        if c.verification:
                            scores["per_criterion"][c.id] = {
                                "score": 0.0,
                                "error": f"Verification exception: {str(e)}"
                            }
                            scores["total_weight"] += c.weight
                    scores["verification"] = {
                        "passed": False,
                        "score": 0.0,
                        "error": f"Verification exception: {str(e)}"
                    }
                    scores["raw"] = scores["points"] / max(scores["total_weight"], 1e-9)
                    scores["pass"] = scores["raw"] >= rubric.scoring.get("min_pass", 0.7)

            # Judge
            judge = None
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
                "judge_id": q.judge_id,
                "judge_prompt": str(jpath),
                "modality": q.modality,
                "split": args.split,
                "aspect": (q.meta or {}).get("aspect"),
                "prompt": prompt,
                "artifact_path": str(art_path),
                "artifact": artifact_used,
                "artifact_randomization": rand_info or None,
                "answer": pred,
                "judge": judge,
            }
            
            # Add verification details if SPICE verification ran
            if q.verification and q.verification.get("enabled") and scores.get("verification"):
                ver = scores["verification"]
                rec["verification_details"] = {
                    "simulation_passed": ver.get("passed", False),
                    "metrics": ver.get("metrics", {}),
                    "error": ver.get("error") if not ver.get("passed") else None
                }
                # Also add top-level metrics for easy access in reports
                rec["verification_metrics"] = ver.get("metrics", {})
                if ver.get("error"):
                    rec["verification_errors"] = [ver.get("error")]
            
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

        import time as _time
        item_timeout = float(os.getenv("EVAL_ITEM_TIMEOUT", "300.0"))  # 5 min per item default
        with ThreadPoolExecutor(max_workers=max(1, int(args.item_workers))) as item_pool:
            futs = []
            for it in items:
                for q in it.questions:
                    futs.append(item_pool.submit(process_q, it, q))
            for i, f in enumerate(futs):
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
                    print(f"[ERROR] Item {i+1}/{len(futs)} failed: {e}", file=sys.stderr, flush=True)
                    # Continue processing other items
                    pass

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
                    try:
                        # Add timeout to prevent indefinite hangs
                        f.result(timeout=model_timeout)
                    except FutureTimeoutError:
                        slug_affected = model_slugs[i] if i < len(model_slugs) else "unknown"
                        print(f"[ERROR] Model {slug_affected} timed out after {model_timeout}s - continuing with remaining models", file=sys.stderr, flush=True)
                        # Continue with other models
                    except Exception as e:
                        slug_affected = model_slugs[i] if i < len(model_slugs) else "unknown"
                        print(f"[ERROR] Model {slug_affected} failed: {e}", file=sys.stderr, flush=True)
                        # Continue with other models

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


if __name__ == "__main__":
    main()

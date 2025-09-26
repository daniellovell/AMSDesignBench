from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import hashlib
import random

from rich import print
from rich.progress import Progress, BarColumn, TimeElapsedColumn, TimeRemainingColumn, MofNCompleteColumn
from concurrent.futures import ThreadPoolExecutor
import threading

# Allow running as script or module
if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from harness.types import Inventory, Question, EvalItem  # type: ignore
    from harness.scoring.rubric import load_rubric, score_answer  # type: ignore
    from harness.scoring.groundedness import groundedness  # type: ignore
    from harness.reporting.render import generate_report, generate_outputs_index  # type: ignore
else:
    from .types import Inventory, Question, EvalItem
    from .scoring.rubric import load_rubric, score_answer
    from .scoring.groundedness import groundedness
    from .reporting.render import generate_report, generate_outputs_index


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


def load_questions(item_dir: Path) -> List[Question]:
    """Load questions; support 'auto' modality expansion from meta.json.
    If a question has modality in {"auto","*","all"} or is missing, expand
    into one question per available modality with inferred artifact paths.
    """
    qfile = item_dir / "questions.jsonl"
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
    available_modalities: List[str] = []
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
            mlist = meta.get("modalities") or []
            tpl_rel = meta.get("template_path") or meta.get("template")
            tpl_dir = (item_dir / tpl_rel).resolve() if isinstance(tpl_rel, str) and tpl_rel.strip() else None
            if isinstance(mlist, list):
                for m in mlist:
                    m_str = str(m)
                    m_canon = canonical_modality.get(m_str, m_str)
                    if m_canon in artifact_by_modality:
                        ap_name = artifact_by_modality[m_canon]
                        exists_local = (item_dir / ap_name).exists()
                        exists_tpl = bool(tpl_dir and (tpl_dir / ap_name).exists())
                        if exists_local or exists_tpl:
                            available_modalities.append(m_canon)
            # Also auto-detect any additional artifacts present (local or template)
            for m, fn in artifact_by_modality.items():
                exists_local = (item_dir / fn).exists()
                exists_tpl = bool(tpl_dir and (tpl_dir / fn).exists())
                if exists_local or exists_tpl:
                    if m not in available_modalities:
                        available_modalities.append(m)
        except Exception:
            pass
    else:
        # Infer by existing artifacts (no meta)
        for m, fn in artifact_by_modality.items():
            if (item_dir / fn).exists():
                available_modalities.append(m)

    out: List[Question] = []
    for line in qfile.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except Exception:
            # As a last resort, try pydantic parse
            try:
                out.append(Question.model_validate_json(line))
            except Exception:
                continue
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
                            new_ap = str(Path(orig_ap) / ap)
                        else:
                            base = Path(orig_ap)
                            # Preserve directory when present; otherwise fall back to the filename
                            parent = base.parent
                            new_ap = str(parent / ap) if str(parent) not in ("", ".") else ap
                    except Exception:
                        new_ap = ap
                    qdict["artifact_path"] = new_ap
                else:
                    # No explicit path provided; use canonical filename for modality
                    qdict["artifact_path"] = ap
                # Keep the original prompt_template; at runtime we can swap it based on modality
                out.append(Question.model_validate(qdict))
        else:
            # Normalize modality and artifact path if missing
            m = canonical_modality.get(str(mod), str(mod))
            if "artifact_path" not in raw and m in artifact_by_modality:
                raw["artifact_path"] = artifact_by_modality[m]
            else:
                # If an artifact_path is provided and points to a directory, append
                # the canonical filename for the modality (supports dir-style inputs).
                try:
                    ap_in = raw.get("artifact_path")
                    if isinstance(ap_in, str) and ap_in.strip() and m in artifact_by_modality:
                        rel = (item_dir / ap_in)
                        if rel.exists() and rel.is_dir():
                            raw["artifact_path"] = str(Path(ap_in) / artifact_by_modality[m])
                except Exception:
                    pass
            raw["modality"] = m
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
                        new_ap = canonical
                        if ap_in:
                            try:
                                rel = (item_dir / ap_in)
                                if rel.exists() and rel.is_dir():
                                    new_ap = str(Path(ap_in) / canonical)
                                else:
                                    # If using bugged SPICE artifact, mirror to bugged filename for modality
                                    if ap_in.endswith("netlist_bug.sp"):
                                        if m2 == "casIR":
                                            new_ap = "netlist_bug.cir"
                                        elif m2 == "cascode":
                                            new_ap = "netlist_bug.cas"
                                    else:
                                        new_ap = canonical
                            except Exception:
                                new_ap = canonical
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
            meta = json.loads(meta_path.read_text())
            tpath = meta.get("template_path") or meta.get("template") or None
            if isinstance(tpath, str) and tpath.strip():
                tpl_dir = (item_dir / tpath).resolve()
                inv_file = tpl_dir / "inventory.json"
                if inv_file.exists():
                    inv = json.loads(inv_file.read_text())
                    return Inventory.model_validate(inv)
        except Exception:
            pass
    # Fallback to local inventory.json
    local = item_dir / "inventory.json"
    if local.exists():
        inv = json.loads(local.read_text())
        return Inventory.model_validate(inv)
    raise FileNotFoundError(f"inventory.json not found for item {item_dir}")


def iter_items(split_dir: Path) -> List[EvalItem]:
    items: List[EvalItem] = []
    # Recursively discover item directories that contain questions, with inventory either local or via template
    for item_dir in sorted([p for p in split_dir.rglob("*") if p.is_dir()]):
        q_path = item_dir / "questions.jsonl"
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
        "--item-index",
        type=int,
        default=0,
        help="1-based item index within the selected scope (after family filter). 0 = all.",
    )
    ap.add_argument("--judge-model", default=None, help="override judge model name")
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
    import yaml
    cfg = yaml.safe_load(Path("bench_config.yaml").read_text()) or {}
    data_root = Path(cfg.get("paths", {}).get("data_root", "data"))
    # Prompts are referenced per-item: resolved as (item_dir/../prompts/<prompt_template>)
    outputs_root = Path(cfg.get("paths", {}).get("outputs_root", "outputs"))
    outputs_root.mkdir(parents=True, exist_ok=True)

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
        cfg_models = (cfg.get("eval", {}) or {}).get("models")
        if isinstance(cfg_models, list) and cfg_models:
            model_specs = [str(m) for m in cfg_models]
        else:
            model_specs = ["dummy"]

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
    rubrics_cache: Dict[str, Any] = {}
    knowledge_cache: Dict[str, str] = {}

    # Scope items by optional family (e.g., debugging, analysis, design)
    search_root = split_dir if not args.family else (split_dir / args.family)
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
    if args.item_index and args.item_index > 0:
        scope_msg += f" item-index=[bold]{args.item_index}[/bold]"
    print(f"[cyan]Evaluating[/cyan]{scope_msg} on models: {', '.join(model_slugs)}")

    write_lock = threading.Lock()
    progress_lock = threading.Lock()
    rubric_lock = threading.Lock()
    knowledge_lock = threading.Lock()

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
        tails: List[str] = []
        in_subckt = False
        subckt_buf: List[str] = []
        subckts: List[List[str]] = []
        current_stmt: List[str] = []
        for ln in raw_lines:
            raw = ln.rstrip('\n')
            s = raw.strip()
            if not s:
                # keep blank lines in tails for aesthetics later
                tails.append(raw)
                continue
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
                subckt_buf.append(raw)
                if low.startswith('.ends'):
                    in_subckt = False
                    subckts.append(subckt_buf)
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
        return '\n'.join(out_lines) + ('\n' if text.endswith('\n') else '')

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
        ident_pat = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*?(?:NMOS|PMOS)[A-Za-z0-9_]*)\b")
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
                raise SystemExit(f"Question {q.id} must specify prompt_template (filename) under ../prompts: {item_dir}")
            ppath = (item_dir.parent / "prompts" / q.prompt_template)
            if not ppath.exists():
                raise SystemExit(f"Prompt template not found for {q.id}: {ppath}")
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
            prompt_tmpl = ppath.read_text()
            # Build example blocks for casIR/cascode modalities
            examples = ""
            # Build or load a plain-language design brief to tell the model exactly what to design
            def _design_brief() -> str:
                # Prefer a local design_brief.txt alongside the item questions
                try:
                    db_path = item_dir / "design_brief.txt"
                    if db_path.exists():
                        txt = db_path.read_text().strip()
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
                        ex1 = (base003 / "netlist.cir").read_text()
                        ex2 = (base006 / "netlist.cir").read_text()
                        examples = (
                            "Example 1 (ota003):\n```json\n" + ex1.strip() + "\n```\n\n" +
                            "Example 2 (ota006):\n```json\n" + ex2.strip() + "\n```\n"
                        )
                    else:
                        # cascode (analog description language)
                        ex1 = (base003 / "netlist.cas").read_text()
                        ex2 = (base006 / "netlist.cas").read_text()
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

            # Artifact
            art_path = item_dir / q.artifact_path
            artifact_text = ""
            if art_path.exists():
                try:
                    artifact_text = art_path.read_text()
                except Exception:
                    artifact_text = ""
            artifact_used = artifact_text
            # For design track, do not leak template artifacts to the model prompt
            if str(q.track).lower() == "design":
                artifact_used = ""
            rand_info: Dict[str, Any] = {}
            # Debugging support: generate bugged artifact from template if requested
            bug_info: Dict[str, Any] = {}
            if str(q.track).lower() == "debugging":
                if q.modality == "spice_netlist":
                    meta_path = item_dir / "meta.json"
                    tpl_net = None
                    if meta_path.exists():
                        try:
                            m = json.loads(meta_path.read_text())
                            tpath = m.get("template_path") or m.get("template")
                            if isinstance(tpath, str) and tpath.strip():
                                tdir = (item_dir / tpath).resolve()
                                tnet = tdir / "netlist.sp"
                                if tnet.exists():
                                    tpl_net = tnet.read_text()
                        except Exception:
                            tpl_net = None
                    base_text = tpl_net or artifact_text
                    meta_seed = None
                    mpath = item_dir / "meta.json"
                    if mpath.exists():
                        try:
                            mm = json.loads(mpath.read_text())
                            ms = mm.get("gen_seed")
                            if isinstance(ms, int):
                                meta_seed = ms
                        except Exception:
                            meta_seed = None
                    if meta_seed is None:
                        meta_seed = int.from_bytes(hashlib.sha256(str(item_dir).encode()).digest()[:8], 'big')
                    bug_seed = int.from_bytes(hashlib.sha256(f"{meta_seed}:{Path(it.item_dir).name}:{q.id}:bug".encode()).digest()[:8], 'big')
                    mutated, dev_id, from_t, to_t = inject_device_swap_spice(base_text or "", bug_seed)
                    if dev_id:
                        artifact_used = mutated
                        bug_info = {"bug_type": "device_polarity_swap", "swapped_id": dev_id, "from_type": from_t, "to_type": to_t}
                    else:
                        artifact_used = base_text
                    try:
                        bug_path = item_dir / "netlist_bug.sp"
                        bug_path.write_text(artifact_used)
                        art_path = bug_path
                    except Exception:
                        pass
                elif q.modality == "casIR":
                    meta_path = item_dir / "meta.json"
                    tpl_cir = None
                    if meta_path.exists():
                        try:
                            m = json.loads(meta_path.read_text())
                            tpath = m.get("template_path") or m.get("template")
                            if isinstance(tpath, str) and tpath.strip():
                                tdir = (item_dir / tpath).resolve()
                                tcir = tdir / "netlist.cir"
                                if tcir.exists():
                                    tpl_cir = tcir.read_text()
                        except Exception:
                            tpl_cir = None
                    base_text = tpl_cir or artifact_text
                    meta_seed = None
                    mpath = item_dir / "meta.json"
                    if mpath.exists():
                        try:
                            mm = json.loads(mpath.read_text())
                            ms = mm.get("gen_seed")
                            if isinstance(ms, int):
                                meta_seed = ms
                        except Exception:
                            meta_seed = None
                    if meta_seed is None:
                        meta_seed = int.from_bytes(hashlib.sha256(str(item_dir).encode()).digest()[:8], 'big')
                    bug_seed = int.from_bytes(hashlib.sha256(f"{meta_seed}:{Path(it.item_dir).name}:{q.id}:bug".encode()).digest()[:8], 'big')
                    mutated, dev_id, from_t, to_t = inject_device_swap_casir(base_text or "", bug_seed)
                    if dev_id:
                        artifact_used = mutated
                        bug_info = {"bug_type": "device_polarity_swap", "swapped_id": dev_id, "from_type": from_t, "to_type": to_t}
                    else:
                        artifact_used = base_text
                    try:
                        bug_path = item_dir / "netlist_bug.cir"
                        bug_path.write_text(artifact_used)
                        art_path = bug_path
                    except Exception:
                        pass
                elif q.modality == "cascode":
                    meta_path = item_dir / "meta.json"
                    tpl_cas = None
                    if meta_path.exists():
                        try:
                            m = json.loads(meta_path.read_text())
                            tpath = m.get("template_path") or m.get("template")
                            if isinstance(tpath, str) and tpath.strip():
                                tdir = (item_dir / tpath).resolve()
                                tcas = tdir / "netlist.cas"
                                if tcas.exists():
                                    tpl_cas = tcas.read_text()
                        except Exception:
                            tpl_cas = None
                    base_text = tpl_cas or artifact_text
                    meta_seed = None
                    mpath = item_dir / "meta.json"
                    if mpath.exists():
                        try:
                            mm = json.loads(mpath.read_text())
                            ms = mm.get("gen_seed")
                            if isinstance(ms, int):
                                meta_seed = ms
                        except Exception:
                            meta_seed = None
                    if meta_seed is None:
                        meta_seed = int.from_bytes(hashlib.sha256(str(item_dir).encode()).digest()[:8], 'big')
                    bug_seed = int.from_bytes(hashlib.sha256(f"{meta_seed}:{Path(it.item_dir).name}:{q.id}:bug".encode()).digest()[:8], 'big')
                    mutated, dev_id, from_t, to_t = inject_device_swap_cascode(base_text or "", bug_seed)
                    if dev_id:
                        artifact_used = mutated
                        bug_info = {"bug_type": "device_polarity_swap", "swapped_id": dev_id, "from_type": from_t, "to_type": to_t}
                    else:
                        artifact_used = base_text
                    try:
                        bug_path = item_dir / "netlist_bug.cas"
                        bug_path.write_text(artifact_used)
                        art_path = bug_path
                    except Exception:
                        pass

            if q.modality == "spice_netlist" and artifact_used:
                meta_seed = None
                mpath = item_dir / "meta.json"
                if mpath.exists():
                    try:
                        m = json.loads(mpath.read_text())
                        ms = m.get("gen_seed")
                        if isinstance(ms, int):
                            meta_seed = ms
                    except Exception:
                        meta_seed = None
                if meta_seed is None:
                    meta_seed = int.from_bytes(hashlib.sha256(str(item_dir).encode()).digest()[:8], 'big')
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
                    }
                ])[0]
            except Exception as e:
                pred = ""
                error_msg = str(getattr(e, "message", e))

            # Rubric
            if not q.rubric_path:
                raise SystemExit(f"Question {q.id} must specify rubric_path relative to item_dir: {item_dir}")
            rpath = (item_dir / q.rubric_path)
            if not rpath.exists():
                raise SystemExit(f"Rubric file not found for {q.id}: {rpath}")
            rkey = str(rpath.resolve())
            with rubric_lock:
                rubric = rubrics_cache.get(rkey)
                if rubric is None:
                    rubrics_cache[rkey] = rubric = load_rubric(rpath)
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
                    # try template answer key (loaded below into refs)
                    try:
                        mpath = item_dir / "meta.json"
                        if mpath.exists():
                            mm = json.loads(mpath.read_text())
                            tpath = mm.get("template_path") or mm.get("template")
                            if isinstance(tpath, str) and tpath.strip():
                                tdir = (item_dir / tpath).resolve()
                                keyp = tdir / "netlist.cir"
                                if keyp.exists():
                                    src_text_for_inv = keyp.read_text()
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

            # Adapt rubric for modalities that should not score grounding
            rjson = rubric.model_dump()
            if q.modality == "cascode":
                for c in rjson.get("criteria", []) or []:
                    if bool(c.get("requires_grounding")):
                        c["weight"] = 0.0
                s = rjson.get("scoring", {}) or {}
                if "hallucination_penalty" in s:
                    s["hallucination_penalty"] = 0.0
                rjson["scoring"] = s
            try:
                from .scoring.rubric import Rubric as RubricModel  # type: ignore
            except Exception:
                from harness.scoring.rubric import Rubric as RubricModel  # type: ignore
            rubric_eff = RubricModel.model_validate(rjson)

            scores = score_answer(pred, rubric_eff, eff_inv)

            # Judge
            judge = None
            kpath = Path("knowledge") / f"{q.rubric_id}.md"
            if not kpath.exists():
                alt = Path("knowledge") / "const_gm_currents.md"
                ktext = alt.read_text() if alt.exists() else ""
            else:
                with knowledge_lock:
                    ktext = knowledge_cache.get(q.rubric_id)
                    if ktext is None:
                        ktext = kpath.read_text()
                        knowledge_cache[q.rubric_id] = ktext
            refs_path = item_dir / "refs.json"
            refs: Dict[str, Any] = {}
            if refs_path.exists():
                try:
                    refs = json.loads(refs_path.read_text())
                except Exception:
                    refs = {}
            if bug_info:
                refs = {**(refs or {}), **bug_info}
            # For design tasks: attach per-modality answer keys to refs for the judge
            if str(q.track).lower() == "design":
                try:
                    mpath = item_dir / "meta.json"
                    if mpath.exists():
                        m = json.loads(mpath.read_text())
                        tpath = m.get("template_path") or m.get("template")
                        if isinstance(tpath, str) and tpath.strip():
                            tdir = (item_dir / tpath).resolve()
                            if q.modality == "spice_netlist":
                                ak = tdir / "netlist.sp"
                                if ak.exists():
                                    refs = {**(refs or {}), "answer_key_spice": ak.read_text()}
                            if q.modality == "casIR":
                                ak = tdir / "netlist.cir"
                                if ak.exists():
                                    refs = {**(refs or {}), "answer_key_casir": ak.read_text()}
                            elif q.modality == "cascode":
                                ak = tdir / "netlist.cas"
                                if ak.exists():
                                    refs = {**(refs or {}), "answer_key_cas": ak.read_text()}
                except Exception:
                    pass
            # Always include minimal context for judge
            refs = {**(refs or {}),
                    "expected_modality": q.modality,
                    "track": q.track,
                    "aspect": (q.meta or {}).get("aspect")}
            try:
                from .scoring.judge_anchored import judge_answer as judge_call  # type: ignore
            except Exception:
                from harness.scoring.judge_anchored import judge_answer as judge_call  # type: ignore
            def _inventory_summary() -> Dict[str, Any]:
                alias_map = eff_inv.alias_map()
                allowed = sorted(set(alias_map.keys()))
                canonical_map = {k: v for k, v in alias_map.items() if k != v}
                
                # Always ensure Cload and CL are in allowed IDs
                if "CL" in alias_map.values():
                    canonical_map.setdefault("Cload", "CL")
                if "Cload" not in allowed:
                    allowed.append("Cload")
                if "CL" not in allowed:
                    allowed.append("CL")
                    
                if any(n.strip().upper() == "0" or n.strip() == "0" for n in eff_inv.nets):
                    for syn in ("GND", "VSS"):
                        canonical_map.setdefault(syn, "0")
                        if syn not in allowed:
                            allowed.append(syn)
                # Append motif 'type' names for casIR so citing types isn't penalized
                try:
                    types = {str(el.type).strip() for el in (eff_inv.elements or {}).values() if getattr(el, "type", None)}
                except Exception:
                    types = set()
                for t in sorted(types):
                    if t and t not in allowed:
                        allowed.append(t)
                summary: Dict[str, Any] = {"allowed_ids": sorted(allowed), "canonical_map": canonical_map}
                if q.modality == "cascode":
                    summary["grounding_disabled"] = True
                return summary

            inv_summary = _inventory_summary()
            if pred:
                try:
                    judge = judge_call(pred, rjson, ktext, refs, inv_summary, model=args.judge_model)
                except Exception:
                    judge = None
            if judge and isinstance(judge.get("scores"), dict):
                j_scores = judge["scores"]
                if "overall" not in judge:
                    judge["overall"] = sum(j_scores.values())/len(j_scores) if j_scores else 0.0

            try:
                topic_str = str(Path(it.item_dir).resolve().relative_to(split_dir.resolve()).parent).replace(os.sep, "/")
            except Exception:
                topic_str = Path(it.item_dir).parent.name

            rec = {
                "model": slug,
                "item_id": item_dir.name,
                "family": topic_str,
                "topic": topic_str,
                "question_id": q.id,
                "track": q.track,
                "rubric_id": q.rubric_id,
                "rubric_path": str(rpath),
                "modality": q.modality,
                "split": args.split,
                "aspect": (q.meta or {}).get("aspect"),
                "prompt": prompt,
                "artifact_path": str(art_path),
                "artifact": artifact_used,
                "artifact_randomization": rand_info or None,
                "answer": pred,
                "scores": scores,
                "judge": judge,
            }
            if error_msg:
                rec["error"] = error_msg
            if judge and isinstance(judge.get("overall", None), (int, float)):
                rec["raw_blended"] = 0.8 * scores["raw"] + 0.2 * float(judge["overall"])

            with write_lock:
                f_combined.write(json.dumps(rec) + "\n")
                model_files[slug].write(json.dumps(rec) + "\n")
                total += 1
            with progress_lock:
                progress.update(task_id, advance=1)

        from concurrent.futures import ThreadPoolExecutor as _TPE
        with _TPE(max_workers=max(1, int(args.item_workers))) as item_pool:
            futs = []
            for it in items:
                for q in it.questions:
                    futs.append(item_pool.submit(process_q, it, q))
            for f in futs:
                f.result()

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
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                futures = [ex.submit(run_for_model, slug) for slug in model_slugs]
                for _ in futures:
                    _.result()

    # Create/overwrite latest pointer
    latest = Path("outputs/latest")
    try:
        if latest.exists() or latest.is_symlink():
            if latest.is_symlink() or latest.is_file():
                latest.unlink()
            else:
                # directory
                pass
        # Use relative target to avoid nested 'outputs/outputs' paths
        latest.symlink_to(out_dir.name)
    except Exception:
        # Windows without symlink perms: copy results
        import shutil
        latest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(results_path, latest / "results.jsonl")
        (outputs_root / "latest_run.txt").write_text(str(out_dir))
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

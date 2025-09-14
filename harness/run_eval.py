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
        "adl": "design.adl",
    }
    # Back-compat: map old modality names
    canonical_modality = {
        "netlist": "spice_netlist",
    }
    available_modalities: List[str] = []
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
            mlist = meta.get("modalities") or []
            if isinstance(mlist, list):
                for m in mlist:
                    m_str = str(m)
                    m_canon = canonical_modality.get(m_str, m_str)
                    if m_canon in artifact_by_modality:
                        # include only if artifact exists
                        ap = item_dir / artifact_by_modality[m_canon]
                        if ap.exists():
                            available_modalities.append(m_canon)
        except Exception:
            pass
    # Fallback: infer by existing artifacts
    if not available_modalities:
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

        mod = raw.get("modality")
        needs_expand = mod in (None, "", "auto", "*", "all")
        base_id = str(raw.get("id", item_dir.name))
        if needs_expand:
            for m in available_modalities:
                ap = artifact_by_modality.get(m)
                if not ap:
                    continue
                qdict = dict(raw)
                qdict["id"] = f"{base_id}_{m}"
                qdict["modality"] = m
                qdict["artifact_path"] = ap
                out.append(Question.model_validate(qdict))
        else:
            # Normalize modality and artifact path if missing
            m = canonical_modality.get(str(mod), str(mod))
            if "artifact_path" not in raw and m in artifact_by_modality:
                raw["artifact_path"] = artifact_by_modality[m]
            raw["modality"] = m
            out.append(Question.model_validate(raw))
    return out


def load_inventory(item_dir: Path) -> Inventory:
    inv = json.loads((item_dir / "inventory.json").read_text())
    return Inventory.model_validate(inv)


def iter_items(split_dir: Path) -> List[EvalItem]:
    items: List[EvalItem] = []
    # Recursively discover item directories that contain required files
    for item_dir in sorted([p for p in split_dir.rglob("*") if p.is_dir()]):
        inv_path = item_dir / "inventory.json"
        q_path = item_dir / "questions.jsonl"
        if not inv_path.exists() or not q_path.exists():
            continue
        inv = load_inventory(item_dir)
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
    ap.add_argument("--judge-model", default=None, help="override judge model name")
    ap.add_argument("--model-workers", type=int, default=0, help="parallel model workers (0 = run all models in parallel)")
    ap.add_argument("--item-workers", type=int, default=8, help="per-model concurrent workers for items/questions")
    args = ap.parse_args()
    # Judge is always enabled; no flag required

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
        # Create a unique slug for outputs
        if name == "openai" and "model" in kwargs and kwargs["model"]:
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

    items = iter_items(split_dir)
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

    print(f"[cyan]Evaluating[/cyan] split=[bold]{args.split}[/bold] on models: {', '.join(model_slugs)}")

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

    def _float_to_unit(val: float, like: str) -> str:
        # Render with the same unit suffix as 'like' if present
        s = like.strip()
        if not s:
            return f"{val:g}"
        suf = s[-1].lower()
        if s.lower().endswith('meg'):
            return f"{val/1e6:g}meg"
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
        if suf in muls:
            return f"{val/muls[suf]:g}{suf}"
        return f"{val:g}"

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
                w_scale_n = 1.0
                l_scale = 1.0
                # Heuristic: NMOS vs PMOS by model token (5th token typical)
                # Fallback: if contains 'pch' treat as PMOS
                is_p = ' pch ' in f' {s.lower()} '
                if is_p:
                    w_scale_n = rnd.uniform(0.85, 1.15)
                else:
                    w_scale_n = rnd.uniform(0.85, 1.15)
                l_scale = rnd.uniform(0.95, 1.05)
                for tok in parts:
                    up = tok.upper()
                    if up.startswith('W=') and w_like:
                        base = _unit_scale_to_float(w_like)
                        if base > 0.0:
                            newv = max(base * w_scale_n, 1e-12)
                            tok = f"W={_float_to_unit(newv, w_like)}"
                    elif up.startswith('L=') and l_like:
                        base = _unit_scale_to_float(l_like)
                        if base > 0.0:
                            newv = max(base * l_scale, 1e-12)
                            tok = f"L={_float_to_unit(newv, l_like)}"
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
                        parts[3] = _float_to_unit(newv, like)
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
            prompt_tmpl = ppath.read_text()
            prompt = prompt_tmpl.format(modality=q.modality)

            # Artifact
            art_path = item_dir / q.artifact_path
            artifact_text = ""
            if art_path.exists():
                try:
                    artifact_text = art_path.read_text()
                except Exception:
                    artifact_text = ""
            artifact_used = artifact_text
            rand_info: Dict[str, Any] = {}
            if q.modality == "spice_netlist" and artifact_text:
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
                artifact_used = randomize_spice(artifact_text, per_item_seed)
                rand_info = {"seed": per_item_seed}

            # Predict
            pred = adapter.predict([
                {
                    "prompt": prompt,
                    "artifact_path": str(item_dir / q.artifact_path),
                    "artifact": artifact_used,
                    "inventory_ids": inv_ids,
                    "question": q.model_dump(),
                }
            ])[0]

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
            scores = score_answer(pred, rubric, it.inventory)

            # Judge
            judge = None
            # Always run judge (anchored scoring)
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
            refs = {}
            if refs_path.exists():
                try:
                    refs = json.loads(refs_path.read_text())
                except Exception:
                    refs = {}
            try:
                from .scoring.judge_anchored import judge_answer as judge_call  # type: ignore
            except Exception:
                from harness.scoring.judge_anchored import judge_answer as judge_call  # type: ignore
            # Build a compact inventory summary for the judge (token-efficient)
            def _inventory_summary() -> Dict[str, Any]:
                alias_map = it.inventory.alias_map()
                allowed = sorted(set(alias_map.keys()))
                canonical_map = {k: v for k, v in alias_map.items() if k != v}
                # Heuristic synonyms to reduce false negatives
                if "CL" in alias_map.values():
                    canonical_map.setdefault("Cload", "CL")
                    if "Cload" not in allowed:
                        allowed.append("Cload")
                # Ground reference synonyms
                if any(n.strip().upper() == "0" or n.strip() == "0" for n in it.inventory.nets):
                    for syn in ("GND", "VSS"):
                        canonical_map.setdefault(syn, "0")
                        if syn not in allowed:
                            allowed.append(syn)
                # Case-insensitive matching hint (judge treats as case-insensitive)
                return {
                    "allowed_ids": sorted(allowed),
                    "canonical_map": canonical_map,
                }

            inv_summary = _inventory_summary()
            try:
                judge = judge_call(pred, rubric.model_dump(), ktext, refs, inv_summary, model=args.judge_model)
            except Exception:
                judge = None
            if judge and isinstance(judge.get("scores"), dict):
                j_scores = judge["scores"]
                if "overall" not in judge:
                    judge["overall"] = sum(j_scores.values())/len(j_scores) if j_scores else 0.0

            # Topic/family
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

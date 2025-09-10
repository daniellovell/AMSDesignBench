from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

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
    for family_dir in sorted([p for p in split_dir.iterdir() if p.is_dir()]):
        for item_dir in sorted([p for p in family_dir.iterdir() if p.is_dir()]):
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
    ap.add_argument("--use-judge", action="store_true", help="enable OpenAI LLM judge for anchored scoring")
    ap.add_argument("--judge-model", default=None, help="override judge model name")
    ap.add_argument("--model-workers", type=int, default=0, help="parallel model workers (0 = run all models in parallel)")
    args = ap.parse_args()

    # Load bench config (YAML)
    import yaml
    cfg = yaml.safe_load(Path("bench_config.yaml").read_text()) or {}
    data_root = Path(cfg.get("paths", {}).get("data_root", "data"))
    prompts_root = Path(cfg.get("paths", {}).get("prompts_root", "prompts"))
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

    def run_for_model(slug: str):
        nonlocal total
        adapter = adapters[slug]
        task_id = model_tasks[slug]
        for it in items:
            item_dir = Path(it.item_dir)
            inv_ids = it.inventory.all_ids()
            for q in it.questions:
                prompt_tmpl = (prompts_root / q.prompt_template).read_text()
                prompt = prompt_tmpl.format(modality=q.modality)
                # Build batch of one to keep interface
                pred = adapter.predict([
                    {
                        "prompt": prompt,
                        "artifact_path": str(item_dir / q.artifact_path),
                        "inventory_ids": inv_ids,
                        "question": q.model_dump(),
                    }
                ])[0]

                # Score
                rkey = q.rubric_id
                if rkey not in rubrics_cache:
                    rubrics_cache[rkey] = load_rubric(Path("rubrics") / f"{rkey}.json")
                rubric = rubrics_cache[rkey]
                scores = score_answer(pred, rubric, it.inventory)

                judge = None
                if args.use_judge:
                    # Load knowledge and refs
                    kpath = Path("knowledge") / f"{q.rubric_id}.md"
                    if not kpath.exists():
                        # fallback: try known alt name for const_gm
                        alt = Path("knowledge") / "const_gm_currents.md"
                        ktext = alt.read_text() if alt.exists() else ""
                    else:
                        ktext = knowledge_cache.setdefault(q.rubric_id, kpath.read_text())
                    refs_path = item_dir / "refs.json"
                    refs = {}
                    if refs_path.exists():
                        try:
                            refs = json.loads(refs_path.read_text())
                        except Exception:
                            refs = {}
                    # Import judge in both script/module contexts
                    try:
                        from .scoring.judge_anchored import judge_answer as judge_call  # type: ignore
                    except Exception:
                        from harness.scoring.judge_anchored import judge_answer as judge_call  # type: ignore
                    judge = judge_call(pred, rubric.model_dump(), ktext, refs, model=args.judge_model)
                    if judge and isinstance(judge.get("scores"), dict):
                        j_scores = judge["scores"]
                        if "overall" not in judge:
                            if j_scores:
                                judge["overall"] = sum(j_scores.values())/len(j_scores)
                            else:
                                judge["overall"] = 0.0

                rec = {
                    "model": slug,
                    "item_id": item_dir.name,
                    "family": Path(it.item_dir).parent.name,
                    "question_id": q.id,
                    "rubric_id": q.rubric_id,
                    "modality": q.modality,
                    "split": args.split,
                    "prompt": prompt,
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

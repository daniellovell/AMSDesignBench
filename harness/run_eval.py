from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from rich import print

# Allow running as script or module
if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from harness.types import Inventory, Question, EvalItem  # type: ignore
    from harness.scoring.rubric import load_rubric, score_answer  # type: ignore
    from harness.scoring.groundedness import groundedness  # type: ignore
else:
    from .types import Inventory, Question, EvalItem
    from .scoring.rubric import load_rubric, score_answer
    from .scoring.groundedness import groundedness


import importlib
ADAPTERS: Dict[str, Any] = {}


def get_adapter(name: str):
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
    return ADAPTERS[name]()


def load_questions(item_dir: Path) -> List[Question]:
    qfile = item_dir / "questions.jsonl"
    qs: List[Question] = []
    for line in qfile.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        qs.append(Question.model_validate_json(line))
    return qs


def load_inventory(item_dir: Path) -> Inventory:
    inv = json.loads((item_dir / "inventory.json").read_text())
    return Inventory.model_validate(inv)


def iter_items(split_dir: Path) -> List[EvalItem]:
    items: List[EvalItem] = []
    for family_dir in sorted([p for p in split_dir.iterdir() if p.is_dir()]):
        for item_dir in sorted([p for p in family_dir.iterdir() if p.is_dir()]):
            inv = load_inventory(item_dir)
            qs = load_questions(item_dir)
            items.append(EvalItem(item_dir=str(item_dir), inventory=inv, questions=qs))
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="dummy", help="adapter name: dummy|openai")
    ap.add_argument("--split", default="dev", help="data split: train|dev|test")
    ap.add_argument("--max-items", type=int, default=0, help="limit items")
    ap.add_argument("--use-judge", action="store_true", help="enable OpenAI LLM judge for anchored scoring")
    ap.add_argument("--judge-model", default=None, help="override judge model name")
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

    adapter = get_adapter(args.model)
    run_id = f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    out_dir = outputs_root / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    results_path = out_dir / "results.jsonl"
    rubrics_cache: Dict[str, Any] = {}
    knowledge_cache: Dict[str, str] = {}

    items = iter_items(split_dir)
    if args.max_items and args.max_items > 0:
        items = items[: args.max_items]

    total = 0
    with results_path.open("w") as f:
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
                        # Simple overall as mean of criteria scores
                        j_scores = judge["scores"]
                        if "overall" not in judge:
                            if j_scores:
                                judge["overall"] = sum(j_scores.values())/len(j_scores)
                            else:
                                judge["overall"] = 0.0

                rec = {
                    "item_id": item_dir.name,
                    "family": Path(it.item_dir).parent.name,
                    "question_id": q.id,
                    "rubric_id": q.rubric_id,
                    "modality": q.modality,
                    "answer": pred,
                    "scores": scores,
                    "judge": judge,
                }
                # blended metric (80% deterministic, 20% judge) if judge available
                if judge and isinstance(judge.get("overall", None), (int, float)):
                    rec["raw_blended"] = 0.8 * scores["raw"] + 0.2 * float(judge["overall"])
                f.write(json.dumps(rec) + "\n")
                total += 1

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

    print(f"[green]Wrote {total} results to[/green] {results_path}")


if __name__ == "__main__":
    main()

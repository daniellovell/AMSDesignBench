from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

sys.path.append(str(Path(__file__).resolve().parents[1]))

import yaml

from harness.utils.template import render_template


def _load_questions(path: Path) -> Iterable[dict]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        raise SystemExit(f"Failed to load {path}: {exc}")
    if isinstance(data, dict):
        if "questions" in data and isinstance(data["questions"], list):
            return data["questions"]
        return [data]
    if isinstance(data, list):
        return data
    raise SystemExit(f"questions.yaml must contain a list or mapping of questions: {path}")


def _resolve_judge_path(item_dir: Path, judge_prompt: str) -> Tuple[Path, str]:
    rel = Path(judge_prompt)
    if rel.is_absolute():
        jpath = rel
    else:
        jpath = (item_dir / rel).resolve()
    if not jpath.exists():
        alt = (item_dir.parent / "judge_prompts" / rel.name).resolve()
        if alt.exists():
            jpath = alt
    return jpath, rel.stem


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate judge prompt and rubric mappings.")
    ap.add_argument("--split", default="dev", help="Data split (default: dev)")
    ap.add_argument("--family", default="analysis", help="Evaluation family (analysis/debugging/design)")
    ap.add_argument(
        "--family-subdir",
        dest="family_subdir",
        default=None,
        help="Optional subdirectory under the family (e.g., feedback, ota). When omitted, validate all subdirectories containing prompts.",
    )
    args = ap.parse_args()

    split_root = Path("data") / args.split
    family_root = split_root / args.family
    if not family_root.exists():
        raise SystemExit(f"Family not found: {family_root}")

    if args.family_subdir:
        subdirs = [args.family_subdir]
    else:
        subdirs = [
            d.name
            for d in sorted(family_root.iterdir())
            if d.is_dir() and (d / "judge_prompts").exists()
        ]
    errors: List[str] = []

    for sub in subdirs:
        base = family_root / sub
        if not base.exists():
            errors.append(f"Missing subdirectory: {base}")
            continue
        judge_dir = base / "judge_prompts"
        if not judge_dir.exists():
            errors.append(f"{base}: missing judge_prompts directory")
        items = [d for d in sorted(base.iterdir()) if d.is_dir() and (d / "questions.yaml").exists()]
        if not items:
            errors.append(f"{base}: no item directories with questions.yaml")
        # Validate each question entry
        for item_dir in items:
            q_path = item_dir / "questions.yaml"
            for entry in _load_questions(q_path):
                if not isinstance(entry, dict):
                    continue
                judge_prompt = entry.get("judge_prompt")
                if not judge_prompt:
                    prompt_template = entry.get("prompt_template")
                    if prompt_template:
                        judge_prompt = str(Path("../judge_prompts") / f"{Path(prompt_template).stem}.md")
                if not judge_prompt:
                    errors.append(f"{q_path}: question {entry.get('id')} missing judge_prompt")
                    continue
                jpath, stem = _resolve_judge_path(item_dir, str(judge_prompt))
                if not jpath.exists():
                    errors.append(f"{q_path}: judge prompt not found: {judge_prompt}")
                    continue
                rubrics_dir = item_dir / "rubrics"
                if not rubrics_dir.exists():
                    errors.append(f"{item_dir}: missing rubrics directory")
                    continue
                yaml_path = rubrics_dir / f"{stem}.yaml"
                if not yaml_path.exists():
                    errors.append(f"{yaml_path}: missing YAML for judge prompt {stem}")
                    continue
                try:
                    rendered_yaml = render_template(
                        yaml_path.read_text(encoding="utf-8"),
                        {},
                        base_dir=yaml_path.parent,
                    )
                    yaml.safe_load(rendered_yaml)
                except Exception as exc:
                    errors.append(f"{yaml_path}: invalid YAML ({exc})")
    if errors:
        print("Judge prompt validation errors:")
        for msg in errors:
            print(" -", msg)
        sys.exit(1)

    checked = ", ".join(subdirs)
    print(f"Judge prompt mapping looks good for {args.split}/{args.family} ({checked}).")


if __name__ == "__main__":
    main()


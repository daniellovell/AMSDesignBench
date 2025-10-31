from __future__ import annotations
import sys
from pathlib import Path
import yaml


def main():
    root = Path("data/dev/analysis/feedback")
    prompts_dir = root / "prompts"
    judge_dir = root / "judge_prompts"
    missing = []
    # 1-1 mapping between question prompts and judge prompts
    for p in sorted(prompts_dir.glob("*.txt")):
        stem = p.stem
        j = judge_dir / f"{stem}.md"
        if not j.exists():
            missing.append(f"missing judge prompt: {j}")
    # Per-item YAML for each judge prompt
    items = [d for d in root.glob("feedback*") if d.is_dir()]
    for it in items:
        rubdir = it / "rubrics"
        for p in sorted(prompts_dir.glob("*.txt")):
            stem = p.stem
            y = rubdir / f"{stem}.yaml"
            if not y.exists():
                missing.append(f"{it.name}: missing vars yaml: {y}")
            else:
                # try loading to catch YAML errors
                try:
                    yaml.safe_load(y.read_text(encoding="utf-8"))
                except Exception as e:
                    missing.append(f"{it.name}: invalid YAML {y}: {e}")
    if missing:
        print("Judge prompt validation errors:")
        for m in missing:
            print(" -", m)
        sys.exit(1)
    print("Judge prompt mapping looks good for dev/analysis/feedback.")


if __name__ == "__main__":
    main()


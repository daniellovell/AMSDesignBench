from __future__ import annotations
from pathlib import Path
from rich import print

try:
    from harness.run_eval import load_questions  # type: ignore
except Exception:
    import sys
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from harness.run_eval import load_questions  # type: ignore


def audit_item(item_dir: Path) -> bool:
    ok = True
    qfile = item_dir / "questions.yaml"
    if not qfile.exists():
        print(f"[red]Missing questions.yaml[/red] in {item_dir}")
        return False
    try:
        questions = load_questions(item_dir)
    except Exception as exc:
        print(f"[red]Failed to load questions for {item_dir}[/red]: {exc}")
        return False

    prompts_dir = item_dir.parent / "prompts"
    for q in questions:
        pt = prompts_dir / q.prompt_template
        if not pt.exists():
            print(f"[red]Missing prompt template[/red] {pt}")
            ok = False
        rpath = item_dir / q.rubric_path
        if not rpath.exists():
            print(f"[red]Missing rubric file[/red] {rpath}")
            ok = False
        apath = item_dir / q.artifact_path
        if not apath.exists():
            print(f"[red]Missing artifact[/red] {apath}")
            ok = False
    return ok


def main():
    root = Path("data")
    bad = 0
    for split in ["train", "dev", "test"]:
        sdir = root/split
        if not sdir.exists():
            continue
        for family in sdir.iterdir():
            if not family.is_dir():
                continue
            for item in family.iterdir():
                if not item.is_dir():
                    continue
                if not audit_item(item):
                    bad += 1
    if bad:
        print(f"[red]{bad} issues found[/red]")
    else:
        print("[green]All items passed basic audit[/green]")


if __name__ == "__main__":
    main()

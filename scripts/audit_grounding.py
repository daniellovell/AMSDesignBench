from __future__ import annotations
import json
from pathlib import Path
from rich import print


def audit_item(item_dir: Path) -> bool:
    inv = json.loads((item_dir/"inventory.json").read_text())
    ids = set(inv.get("elements", {}).keys()) | set(inv.get("blocks", {}).keys()) | set(inv.get("nets", []))
    ok = True
    for line in (item_dir/"questions.jsonl").read_text().splitlines():
        q = json.loads(line)
        # Basic check: prompt template exists
        pt = Path("prompts")/q["prompt_template"]
        if not pt.exists():
            print(f"[red]Missing prompt template[/red] {pt}")
            ok = False
        # Artifact path exists
        if not (item_dir/q["artifact_path"]).exists():
            print(f"[red]Missing artifact[/red] {(item_dir/q['artifact_path'])}")
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


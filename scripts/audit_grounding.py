from __future__ import annotations
import json
from pathlib import Path
from rich import print


ARTIFACT_BY_MODALITY = {
    "spice_netlist": "netlist.sp",
    "veriloga": "veriloga.va",
    "adl": "design.adl",
}

CANONICAL = {"netlist": "spice_netlist"}


def available_modalities(item_dir: Path) -> list[str]:
    metas = item_dir / "meta.json"
    mods: list[str] = []
    if metas.exists():
        try:
            meta = json.loads(metas.read_text())
            for m in meta.get("modalities", []) or []:
                m = CANONICAL.get(str(m), str(m))
                fn = ARTIFACT_BY_MODALITY.get(m)
                if fn and (item_dir / fn).exists():
                    mods.append(m)
        except Exception:
            pass
    if not mods:
        for m, fn in ARTIFACT_BY_MODALITY.items():
            if (item_dir / fn).exists():
                mods.append(m)
    return mods


def audit_item(item_dir: Path) -> bool:
    ok = True
    qfile = item_dir / "questions.jsonl"
    if not qfile.exists():
        print(f"[red]Missing questions.jsonl[/red] in {item_dir}")
        return False
    # Prompt template(s)
    for line in qfile.read_text().splitlines():
        if not line.strip():
            continue
        try:
            q = json.loads(line)
        except Exception:
            print(f"[red]Malformed question JSON[/red] in {qfile}")
            ok = False
            continue
        pt = Path("prompts") / q.get("prompt_template", "")
        if not pt.exists():
            print(f"[red]Missing prompt template[/red] {pt}")
            ok = False
        # Rubric check
        rid = q.get("rubric_id")
        if not rid or not (Path("rubrics") / f"{rid}.json").exists():
            print(f"[red]Missing rubric[/red] {rid} for {item_dir}")
            ok = False
        # Artifact check (skip if auto modality)
        mod = q.get("modality")
        if mod and mod not in ("auto", "*", "all"):
            m = CANONICAL.get(str(mod), str(mod))
            ap = q.get("artifact_path") or ARTIFACT_BY_MODALITY.get(m)
            if ap and not (item_dir / ap).exists():
                print(f"[red]Missing artifact[/red] {(item_dir / ap)}")
                ok = False

    # For auto expansion, verify artifacts for available modalities exist
    mods = available_modalities(item_dir)
    for m in mods:
        ap = ARTIFACT_BY_MODALITY.get(m)
        if ap and not (item_dir / ap).exists():
            print(f"[red]Expected artifact for modality {m} missing[/red]: {(item_dir / ap)}")
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

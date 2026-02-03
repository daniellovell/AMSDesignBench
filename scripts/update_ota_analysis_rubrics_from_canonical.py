#!/usr/bin/env python3
"""
Update OTA analysis short-form rubric relation_target strings to match the canonical formulas
used for MCQs, but expressed in the non-shuffled template instance namespace.

This script is intentionally simple: rubric files are 2-line YAML stubs:
  relation_target: "..."
  {path:_ota_rubric_template.yaml}
"""

from __future__ import annotations

import re
from pathlib import Path


def _mc_to_rubric(expr: str) -> str:
    # Convert gm_{M1} -> gm_M1, ro_{Mp1} -> ro_Mp1, γ_{M2} -> γ_M2, (W/L)_{M6} -> (W/L)_M6
    if not expr:
        return expr
    expr = re.sub(r"\{([A-Za-z0-9_]+)\}", r"\1", expr)
    return expr


def _strip_relation_equivalents_block(txt: str) -> str:
    """
    Remove an existing relation_equivalents block if present.
    Supports:
      relation_equivalents: ["a", "b"]
      relation_equivalents:
        - "a"
        - "b"
    """
    # Remove flow-style
    txt = re.sub(r"^relation_equivalents:\s*\\[.*?\\]\\s*$\\n?", "", txt, flags=re.MULTILINE)
    # Remove block-style (until next non-indented key/include line)
    txt = re.sub(
        r"^relation_equivalents:\\s*$\\n(?:^\\s{2,}-\\s+.*$\\n)+",
        "",
        txt,
        flags=re.MULTILINE,
    )
    # Remove block-scalar style (relation_equivalents: | ... indented lines ...)
    txt = re.sub(
        r"^relation_equivalents:\\s*\\|.*$\\n(?:^\\s{2,}.*$\\n)+",
        "",
        txt,
        flags=re.MULTILINE,
    )
    return txt


def main() -> None:
    # Import from the generator so we only have one source of truth.
    # We avoid package imports; load by file path so this works without PYTHONPATH tweaks.
    import importlib.util
    gen_path = Path(__file__).parent / "generate_mc_answer_keys.py"
    spec = importlib.util.spec_from_file_location("generate_mc_answer_keys", gen_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Failed to load generator module from {gen_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    _ota_canonical_mc_formula = getattr(mod, "_ota_canonical_mc_formula")
    _ota_power_equivalents_mc = getattr(mod, "_ota_power_equivalents_mc")

    root = Path(__file__).parent.parent
    analysis_dir = root / "data" / "dev" / "analysis" / "ota"

    rubric_map = {
        "gain_dc": "ota_dc_gain.yaml",
        "rout": "ota_rout.yaml",
        "psrr": "ota_psrr.yaml",
        "noise_white": "ota_noise_white.yaml",
        "power_quiescent": "ota_power_quiescent.yaml",
        # gbw lives in gbw_one_stage.yaml or gbw_two_stage.yaml depending on OTA
        "gbw": None,
    }

    ota_ids = sorted([p.name for p in analysis_dir.iterdir() if p.is_dir() and p.name.startswith("ota")])
    updated = 0
    for ota_id in ota_ids:
        rub_dir = analysis_dir / ota_id / "rubrics"
        if not rub_dir.exists():
            continue

        for aspect, fname in rubric_map.items():
            if aspect == "gbw":
                # Prefer gbw_two_stage if present, else gbw_one_stage
                for cand in ("gbw_two_stage.yaml", "gbw_one_stage.yaml"):
                    p = rub_dir / cand
                    if p.exists():
                        fname = cand
                        break
                if fname is None:
                    continue

            path = rub_dir / str(fname)
            if not path.exists():
                continue

            canon = _ota_canonical_mc_formula(ota_id, aspect)
            if not canon:
                raise SystemExit(f"Missing canonical formula for {ota_id} aspect={aspect}")

            target = _mc_to_rubric(canon)
            txt = path.read_text(encoding="utf-8")
            txt = _strip_relation_equivalents_block(txt)
            # Replace only the relation_target line (first occurrence).
            new_txt, n = re.subn(
                r'^relation_target:\s*".*?"\s*$',
                f'relation_target: "{target}"',
                txt,
                count=1,
                flags=re.MULTILINE,
            )
            if n != 1:
                raise SystemExit(f"Unexpected rubric format in {path} (matches={n})")

            # For quiescent power, include ALL acceptable DC-equivalent expressions in the judge prompt.
            if aspect == "power_quiescent":
                eqs = list(_ota_power_equivalents_mc(ota_id) or [])
                eqs_r = [_mc_to_rubric(x) for x in eqs if x]
                # Drop the target itself; it's already shown as relation_target.
                eqs_r = [x for x in eqs_r if x != target]
                # Use a block-scalar string so run_eval's `str()` conversion keeps newlines.
                # This renders nicely in the judge prompt as a bullet list.
                if not eqs_r:
                    eqs_block = "relation_equivalents: |\n  (none)"
                else:
                    eq_lines = "\n".join([f"  - {x}" for x in eqs_r])
                    eqs_block = "relation_equivalents: |\n" + eq_lines
                # IMPORTANT: The per-OTA include (_ota_rubric_template.yaml) defines a default
                # relation_equivalents string. To override it, we must place our relation_equivalents
                # *after* the include (i.e., later in the YAML).
                # Append at end (on a new line) to guarantee it wins.
                if not new_txt.endswith("\n"):
                    new_txt += "\n"
                new_txt = new_txt + eqs_block + "\n"
            if new_txt != txt:
                path.write_text(new_txt, encoding="utf-8")
                updated += 1

    print(f"Updated {updated} rubric files.")


if __name__ == "__main__":
    main()



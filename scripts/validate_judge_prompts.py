from __future__ import annotations

import argparse
import re
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


def validate_template_includes(template_path: Path, base_dir: Path, visited: set[Path] | None = None, depth: int = 0) -> List[str]:
    """Validate that all {path:...} includes exist. Recursively validates nested includes."""
    errors = []
    if visited is None:
        visited = set()
    
    # Guard against cycles and excessive depth
    if depth > 8:
        return [f"{template_path}: include depth exceeds limit (possible circular dependency)"]
    
    if template_path in visited:
        return [f"{template_path}: circular include dependency detected"]
    
    visited.add(template_path)
    
    try:
        content = template_path.read_text(encoding="utf-8")
    except Exception as exc:
        return [f"{template_path}: failed to read template ({exc})"]
    
    # Use the same pattern as harness/utils/template.py
    includes = re.findall(r"\{path:([^}]+)\}", content)
    
    for include in includes:
        include = include.strip()
        include_path = Path(include)
        # Resolve relative to base_dir if not absolute
        if not include_path.is_absolute():
            include_path = (base_dir / include_path).resolve()
        else:
            include_path = include_path.resolve()
        
        if not include_path.exists():
            errors.append(f"{template_path}: include not found: {include} (resolved to {include_path})")
        else:
            # Recursively validate nested includes
            nested_errors = validate_template_includes(include_path, include_path.parent, visited, depth + 1)
            errors.extend(nested_errors)
    
    return errors


def validate_family(split_root: Path, family: str, family_subdir: str | None = None) -> List[str]:
    """Validate a single family. Returns list of error messages."""
    family_root = split_root / family
    if not family_root.exists():
        return [f"Family not found: {family_root}"]

    if family_subdir:
        subdirs = [family_subdir]
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
                
                # Validate template includes before rendering
                include_errors = validate_template_includes(jpath, jpath.parent)
                errors.extend(include_errors)
                
                rubrics_dir = item_dir / "rubrics"
                if not rubrics_dir.exists():
                    errors.append(f"{item_dir}: missing rubrics directory")
                    continue
                yaml_path = rubrics_dir / f"{stem}.yaml"
                if not yaml_path.exists():
                    errors.append(f"{yaml_path}: missing YAML for judge prompt {stem}")
                    continue
                try:
                    # First, validate YAML syntax by rendering any template variables in the YAML itself
                    # Note: Runtime variables in YAML are expected at runtime, so we provide mock values for validation
                    # Mock runtime variables that might be used in YAML files
                    # These are for OTA device swap debugging (runtime-generated)
                    mock_runtime_vars = {
                        "swapped_id": "M1",
                        "from_type": "PMOS",
                        "to_type": "NMOS",
                        "bug_type": "device_polarity_swap",
                    }
                    
                    try:
                        rendered_yaml = render_template(
                            yaml_path.read_text(encoding="utf-8"),
                            mock_runtime_vars,
                            base_dir=yaml_path.parent,
                        )
                    except ValueError as ve:
                        # If we still get a runtime variable error, it's a new runtime var we don't have a mock for
                        # In this case, try to continue with empty vars
                        # TODO: Consider using a custom exception class (e.g., MissingRuntimeVariableError) in template.py
                        #       for a more robust contract between modules instead of string matching
                        if "Runtime variable" in str(ve) and "not found in vars" in str(ve):
                            # Try with empty vars and let runtime vars remain unresolved
                            # This will cause YAML parsing issues, but we'll catch that below
                            rendered_yaml = yaml_path.read_text(encoding="utf-8")
                            # Replace runtime directives with placeholder for YAML parsing
                            rendered_yaml = re.sub(r"\{runtime:[a-zA-Z0-9_]+\}", '""', rendered_yaml)
                        else:
                            raise
                    
                    yaml_data = yaml.safe_load(rendered_yaml)
                    if yaml_data is None:
                        yaml_data = {}
                    
                    # Convert YAML data to string values for template rendering
                    yaml_vars = {k: str(v) for k, v in yaml_data.items()}
                    
                    # Add mock runtime vars to yaml_vars for judge prompt rendering
                    yaml_vars.update(mock_runtime_vars)
                    
                    # Render the judge prompt template with the YAML data
                    # Note: Runtime variables (e.g., {runtime:swapped_id}) are provided at runtime,
                    # so we catch ValueError for missing runtime vars during validation
                    try:
                        judge_content = render_template(
                            jpath.read_text(encoding="utf-8"),
                            yaml_vars,
                            base_dir=jpath.parent,
                        )
                    except ValueError as ve:
                        # Check if this is a runtime variable error
                        # TODO: Consider using a custom exception class (e.g., MissingRuntimeVariableError) in template.py
                        #       for a more robust contract between modules instead of string matching
                        error_msg = str(ve)
                        if "Runtime variable" in error_msg and "not found in vars" in error_msg:
                            # Parse the error message to extract the missing runtime variable name
                            # Format: "Runtime variable '{key}' not found in vars"
                            match = re.search(r"Runtime variable '([a-zA-Z0-9_]+)' not found in vars", error_msg)
                            if match:
                                missing_runtime_key = match.group(1)
                                errors.append(
                                    f"{jpath}: missing runtime variable binding: {missing_runtime_key} "
                                    f"(expected at runtime, not in validation mock vars)"
                                )
                            else:
                                # Fallback if message format changes
                                errors.append(
                                    f"{jpath}: missing runtime variable binding (error: {error_msg})"
                                )
                            # Skip unreplaced-variable check for this prompt since we couldn't render it
                            continue
                        else:
                            # Re-raise non-runtime ValueError exceptions unchanged
                            raise
                    
                    # Check for unreplaced template variables
                    # Use the same pattern as harness/utils/template.py: only alphanumeric + underscore
                    # Note: Runtime directives {runtime:key} are not matched by this regex (no colon in character class)
                    unreplaced = re.findall(r"\{([a-zA-Z0-9_]+)\}", judge_content)
                    if unreplaced:
                        errors.append(
                            f"{jpath}: unreplaced variables: {', '.join(sorted(set(unreplaced)))}"
                        )
                except Exception as exc:
                    errors.append(f"{yaml_path}: template rendering failed ({exc})")
    
    return errors


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate judge prompt and rubric mappings.")
    ap.add_argument("--split", default="dev", help="Data split (default: dev)")
    ap.add_argument(
        "--family",
        default="analysis",
        help="Evaluation family (analysis/debugging/design) or 'all' to validate all families",
    )
    ap.add_argument(
        "--family-subdir",
        dest="family_subdir",
        default=None,
        help="Optional subdirectory under the family (e.g., feedback, ota). When omitted, validate all subdirectories containing prompts.",
    )
    args = ap.parse_args()

    split_root = Path("data") / args.split
    if not split_root.exists():
        raise SystemExit(f"Split not found: {split_root}")

    # Determine which families to validate
    if args.family.lower() == "all":
        # Discover all families by scanning for directories with judge_prompts
        # A family has judge_prompts if:
        # 1. It has a judge_prompts directory directly, OR
        # 2. It has subdirectories containing judge_prompts
        families = []
        for d in sorted(split_root.iterdir()):
            if not d.is_dir():
                continue
            # Check if family has judge_prompts directly
            if (d / "judge_prompts").exists():
                families.append(d.name)
                continue
            # Check if any subdirectory has judge_prompts
            if any((d / subdir / "judge_prompts").exists() for subdir in d.iterdir() if subdir.is_dir()):
                families.append(d.name)
        
        if not families:
            raise SystemExit(f"No families found in {split_root}")
    else:
        families = [args.family]

    all_errors: List[str] = []
    validated_subdirs: List[str] = []

    # Validate each family
    for family in families:
        family_errors = validate_family(split_root, family, args.family_subdir)
        all_errors.extend(family_errors)
        
        # Track which subdirs were validated for reporting
        family_root = split_root / family
        if family_root.exists():
            if args.family_subdir:
                validated_subdirs.append(f"{family}/{args.family_subdir}")
            else:
                subdirs = [
                    d.name
                    for d in sorted(family_root.iterdir())
                    if d.is_dir() and (d / "judge_prompts").exists()
                ]
                if subdirs:
                    validated_subdirs.extend([f"{family}/{sub}" for sub in subdirs])

    if all_errors:
        print("Judge prompt validation errors:")
        for msg in all_errors:
            print(" -", msg)
        sys.exit(1)

    if args.family.lower() == "all":
        checked = ", ".join(sorted(set(validated_subdirs)))
        print(f"Judge prompt mapping looks good for {args.split} (all families: {checked}).")
    else:
        checked = ", ".join([s for s in validated_subdirs if s.startswith(f"{args.family}/")])
        print(f"Judge prompt mapping looks good for {args.split}/{args.family} ({checked}).")


if __name__ == "__main__":
    main()


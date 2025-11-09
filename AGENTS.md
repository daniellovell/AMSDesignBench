# Repository Guidelines

## Project Structure & Module Organization
- `harness/` — core runner and library code: `run_eval.py`, `adapters/` (LLM backends), `scoring/` (rubrics, groundedness, `judge_anchored.py`), `reporting/` (HTML, summaries), `utils/`.
- `data/<split>/` — benchmark items (`analysis/`, `design/`, `debugging/`), with `questions.yaml`, `meta.json`, and template indirection to `data/<split>/templates/...`.
- `scripts/` — utilities like `smoke_test.py`, `build_items.py`, `audit_grounding.py`, `validate_judge_prompts.py`.
- `knowledge/` — canonical fact sheets used by the judge.
- `ltspice/` — reference schematics.
- `bench_config.yaml` — paths and model config; outputs go to `outputs/<timestamp>/` and `outputs/latest/`.

### Evaluation Prompts (Given to Models Under Test)
- **Location**: `data/<split>/<family>/<subdir>/prompts/<prompt_template>.txt`
  - Example: `data/dev/design/ota/prompts/design_ota.txt`
- Referenced in `questions.yaml` via `prompt_template` field (relative path from item directory).

### LLM-as-Judge System
The evaluation uses an LLM judge (via OpenAI API) to score model responses. Files are organized as follows:

- **Judge prompt templates**: `data/<split>/<family>/<subdir>/judge_prompts/<judge_prompt>.md`
  - Example: `data/dev/design/ota/judge_prompts/design_ota_template.md`
  - Supports template variables `{var_name}` and includes via `{path:relative/path.md}`
  
- **Rubric YAML (variables)**: `data/<split>/<family>/<subdir>/<item>/rubrics/<judge_id>.yaml`
  - Example: `data/dev/design/ota/ota001/rubrics/design_5t_ota.yaml`
  - Contains variable definitions used to render judge prompt templates
  
- **How it works** (`harness/scoring/judge_anchored.py`):
  1. Load judge prompt template from `judge_prompts/<judge_prompt>.md`
  2. Load rubric YAML from `rubrics/<judge_id>.yaml` 
  3. Render judge prompt template with YAML variables
  4. Send rendered prompt + context (refs, answer, inventory) to judge LLM API
  5. Judge returns JSON: `{"scores": {"<criterion>": <0..1>, ...}, "overall": <0..1>}`

## Build, Test, and Development Commands
- Create env and install: `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`.
- Quick smoke run (dummy model): `python scripts/smoke_test.py`.
- Manual eval: `python -m harness.run_eval --model dummy --split dev`.
- Multi‑model: `python -m harness.run_eval --models openai:gpt-4o-mini dummy --split dev --model-workers 2`.
- Performance profiling: append `--enable-profiling` to emit `[PROFILE]` timing logs (adapters, rate limiting, judge, thread pools) to stderr and persist `profiling/` logs + summary under the run directory.
- Summarize JSONL: `python harness/reporting/summarize.py outputs/latest/results.jsonl`.
- Report location: `outputs/latest/report/index.html`.

## Coding Style & Naming Conventions
- Python 3.10+, 4‑space indentation, PEP 8 naming: modules/functions/variables `snake_case`, classes `PascalCase`, constants `UPPER_CASE`.
- Prefer type hints (Pydantic v2 models in `harness/types.py`).
- Keep adapters minimal; add new backends under `harness/adapters/` with a `build(**kwargs)` factory.

## Testing Guidelines
- No formal pytest suite. Use `scripts/smoke_test.py` to verify end‑to‑end.
- For targeted checks, run `harness/run_eval.py` on a single split/item and inspect `outputs/latest/results.jsonl` plus the rendered report.
- Randomization is deterministic per item via hashing; expect stable results given fixed inputs.

### Judge Prompt Validation
- **Use before committing**: Run `scripts/validate_judge_prompts.py` to validate judge prompts and rubric YAML mappings.
- **Checks**: File existence, YAML syntax, template variable completeness, and that all template includes resolve correctly.
- **Usage**: `python scripts/validate_judge_prompts.py --split dev --family <family|all> [--family-subdir <subdir>]`
  - Example: `--split dev --family all` (validates all families: `dev/analysis`, `dev/debugging`, `dev/design`)
  - Example: `--split dev --family design --family-subdir feedback` (validates `dev/design/feedback`)
  - Example: `--split dev --family analysis` (validates all subdirectories under `dev/analysis`)

## Commit & Pull Request Guidelines
- Commits: imperative, concise subject (≤72 chars), body explains motivation and scope. Example: “Support auto modality on .cas and .cir”.
- PRs: include what/why, sample commands used, and a brief note or screenshot pointing to `outputs/latest/report/index.html`. Link related issues and note any data/template changes.

## Security & Configuration Tips
- Set API keys via env vars: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`.
- Edit `bench_config.yaml` rather than hard‑coding paths. Avoid committing secrets or local outputs.

AMS Oral Knowledge LLM Bench
=================================

Qualitative, symbolic, and grounded benchmark for analog/mixed-signal IC design. Models read artifacts (SPICE netlists; other modalities are currently shelved), reason symbolically, and propose improvements. Scoring is rubric-based with groundedness checks; an LLM judge is always enabled for anchored scoring.

Quick start
- Create a Python 3.10+ venv and install `requirements.txt`:
  ```bash
  python3 -m venv venv
  source venv/bin/activate  # On Windows: venv\Scripts\activate
  pip install -r requirements.txt
  ```
- Set API keys (choose one or more adapters):
  - OpenAI (required for OpenAI adapter and for the judge if enabled):
    - `export OPENAI_API_KEY=...`
  - Anthropic (for Anthropic adapter):
    - `export ANTHROPIC_API_KEY=...`
  - OpenRouter (multi-vendor via one endpoint):
    - `export OPENROUTER_API_KEY=...`
    - Optional: `export OPENROUTER_REFERER=...` and `export OPENROUTER_TITLE=...`

- Run a model:
  - Single model: `python harness/run_eval.py --model dummy --split dev`.
  - Multiple models: `python harness/run_eval.py --models dummy openai:gpt-4o-mini --split dev`.
    - Also supported: comma-separated via `--model openai:gpt-4o-mini,dummy`.
    - Or set in `bench_config.yaml` under `eval.models: ["dummy", "openai:gpt-4o-mini"]` and run without `--model*` flags.
- Parallelism:
  - Across models: runs in parallel by default. Control with `--model-workers N` (0 = all models concurrently).
  - Within a model: items/questions run concurrently. Control with `--item-workers N` (default 8).
- While running, a progress bar shows per-model progress. Results are written to a timestamped folder under `outputs/` with:
  - `combined_results.jsonl`: all models combined (also copied to `outputs/latest/results.jsonl` for back-compat).
  - Per-model files at `outputs/<run_id>/<model_slug>/results.jsonl`.
- Summaries:
  - Per-model: `python harness/reporting/summarize.py outputs/latest/<model_slug>/results.jsonl`.
  - Cross-model: `python harness/reporting/compare.py outputs/latest/combined_results.jsonl`.
  - Render compact human-readable report (HTML+CSV+MD):
    - Auto-rendered at the end of each eval; open `outputs/latest/report/index.html`.
    - Re-render manually: `python harness/reporting/render.py outputs/latest/combined_results.jsonl`.

Layout
- `bench_config.yaml`: bench and rubric versions, seeds, limits.
- Prompts live under each family: e.g., `data/<split>/analysis/ota/prompts/`.
- `knowledge/`: canonical fact sheets to anchor judging.
- `data/{train,dev,test}/<family>/<item_id>/`: artifacts + inventories + questions + item-local rubrics under `rubrics/`.
- `harness/`: adapters, scoring, reporting, runner.
- `scripts/`: item builder, audits, smoke test.

Design goals
- Symbolic, not numeric; grounded by inventory; rubric-based scoring (no simulator required).

Notes
- Current dataset: OTA analysis tasks (GBW, Rout, and Output Swing) under `data/dev/analysis/ota/*`.
- ADL and Verilog-A modalities are temporarily shelved; SPICE netlists are used for analysis.
- Deterministic rubric scoring + groundedness/hallucination checks, with an LLM judge.

Adapters and models
- Model spec format: `adapter:model_name`. Examples:
  - OpenAI: `openai:gpt-4o-mini`, `openai:gpt-5-mini`, `openai:gpt-5`
  - Anthropic: `anthropic:claude-3-5-sonnet-latest`
  - OpenRouter: `openrouter:anthropic/claude-3-5-sonnet-latest`, `openrouter:openai/gpt-5-mini`
- Environment variables (required and optional):
  - OpenAI:
    - Required: `OPENAI_API_KEY`
    - Optional: `OPENAI_MODEL` (default `gpt-4o-mini`), `OPENAI_TEMPERATURE`, `OPENAI_MAX_TOKENS`
    - Judge: `OPENAI_JUDGE_MODEL`, `OPENAI_JUDGE_TEMPERATURE`, `OPENAI_JUDGE_MAX_TOKENS`
  - Anthropic:
    - Required: `ANTHROPIC_API_KEY`
    - Optional: `ANTHROPIC_MODEL` (default `claude-3-5-sonnet-latest`), `ANTHROPIC_TEMPERATURE`, `ANTHROPIC_MAX_TOKENS` (adapter supplies a default if unset)
  - OpenRouter:
    - Required: `OPENROUTER_API_KEY`
    - Optional: `OPENROUTER_MODEL`, `OPENROUTER_TEMPERATURE`, `OPENROUTER_MAX_TOKENS`, `OPENROUTER_REFERER`, `OPENROUTER_TITLE`
- Notes on model quirks handled by the harness:
  - OpenAI gpt‑5 family: rejects non-default `temperature` and prefers `max_completion_tokens`. The adapter auto-retries and, for gpt‑5, avoids hard caps to prevent empty outputs dominated by reasoning tokens.
  - Anthropic Messages API: requires `max_tokens`. We pass a sensible default or your `ANTHROPIC_MAX_TOKENS`.

OpenAI adapter and Judge
- Run with OpenAI (default model): `python harness/run_eval.py --model openai --split dev`.
- Specify a concrete OpenAI model: `--model openai:gpt-4o-mini` or include in `--models`.
- Judge is always on; optionally set `--judge-model gpt-4o-mini`. Results include `judge.overall`.

Knowledge Anchors
- The bench loads an optional knowledge anchor for each question by rubric id: `knowledge/<rubric_id>.md`.
- The runner sends the rubric JSON, the knowledge snippet, refs (if any), the answer, and a compact inventory summary to the judge.
- The judge returns per‑criterion scores in [0,1] and an overall; the harness records them.
- If no rubric‑specific file exists, the judge falls back to a generic anchor when available.

Anthropic adapter
- Run Anthropic directly: `python harness/run_eval.py --model anthropic:claude-3-5-sonnet-latest --split dev`.
- Uses the Messages API (`system`, `messages`, `max_tokens`); text is assembled from returned content blocks.

OpenRouter adapter
- Run via OpenRouter (multi-vendor): `python harness/run_eval.py --model openrouter:anthropic/claude-3-5-sonnet-latest --split dev`.
- Uses an OpenAI-compatible Chat Completions client pointed at `https://openrouter.ai/api/v1`.

Human-readable report
- Compact HTML tables summarize models and per-question scores; side-by-side per-item pages include:
  - Full prompt text, model answers (collapsible), per-criterion scores with grounding ratios, hallucination penalties, judge per-criterion and overall.
- Generate via: `python harness/reporting/render.py outputs/latest/combined_results.jsonl`.

**How Evaluation Works**
- Models: specify via `--models` or `bench_config.yaml`. Each adapter runs over all items; runs parallelize across models.
- Questions: each item defines one or more analysis questions with a rubric and required sections.
- Rubrics: each question references an item-local rubric JSON via `rubric_path` (relative to the item directory). Global rubrics are not used.
- Prompts: the runner embeds the artifact and prompt template; required sections must be present in responses.
- Scoring: a deterministic rubric matches required statements and checks groundedness (referencing real IDs). A judge is always invoked for anchored, knowledge-aware scoring; reports display judge scores.
- Reports: results are written to `outputs/<run_id>/` and auto-rendered to `outputs/latest/report/index.html`.

**Pretraining/Overfitting Mitigations**
- Mandatory SPICE randomization: before prompting, the SPICE netlist is randomized per item/question and embedded in the prompt.
  - Shuffles device/source statement order while preserving `.model/.param/.control` headers and `.SUBCKT … .ENDS` blocks; continuation lines are kept with their device.
  - Jitters sizes within safe bounds: MOS `W` *[0.85, 1.15], `L` *[0.95, 1.05]; capacitors *[0.7, 1.3]. Units are preserved.
  - Connectivity and topology are unchanged; instance/net names remain stable for groundedness.
  - Deterministic per-item seeds: derived from `meta.gen_seed` or a stable hash; the seed used is recorded in results as `artifact_randomization.seed`.
- Topology identification required: prompts include a mandatory `Topology` section; rubrics require correct topology identification scoped to that section (prevents accidental credit elsewhere in the answer).
- Groundedness checks: answers must cite real inventory IDs; hallucinated IDs incur penalties.

**Reproducibility**
- Runs are deterministic given the dataset and seeds. Randomization uses per-item seeds derived from `meta.json` (or a stable hash fallback) and is logged with each result.

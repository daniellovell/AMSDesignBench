AMS Oral Knowledge LLM Bench
=================================

Qualitative, symbolic, and grounded benchmark for analog/mixed-signal IC design. Models read artifacts (SPICE netlists; other modalities are currently shelved), reason symbolically, and propose improvements. Scoring is rubric-based with groundedness checks; an optional LLM judge can be enabled.

Quick start
- Create a Python 3.10+ venv and install `requirements.txt`.
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
- Current dataset: OTA analysis tasks (GBW and Rout) under `data/dev/analysis/ota/*`.
- ADL and Verilog-A modalities are temporarily shelved; SPICE netlists are used for analysis.
- Deterministic rubric scoring + groundedness/hallucination checks by default; optional LLM judge available.

OpenAI adapter and Judge
- Env vars: set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` (default `gpt-4o-mini`).
- Run with OpenAI (default model): `python harness/run_eval.py --model openai --split dev`.
- Specify a concrete OpenAI model: `--model openai:gpt-4o-mini` or include in `--models`.
- Enable LLM judge: add `--use-judge` (optionally `--judge-model gpt-4o-mini`).
- Results include `judge.overall` and `raw_blended` (80% deterministic + 20% judge).

Human-readable report
- Compact HTML tables summarize models and per-question scores; side-by-side per-item pages include:
  - Full prompt text, model answers (collapsible), per-criterion scores with grounding ratios, hallucination penalties, judge per-criterion and overall.
- Generate via: `python harness/reporting/render.py outputs/latest/combined_results.jsonl`.

**How Evaluation Works**
- Models: specify via `--models` or `bench_config.yaml`. Each adapter runs over all items; runs parallelize across models.
- Questions: each item defines one or more analysis questions with a rubric and required sections.
- Rubrics: each question references an item-local rubric JSON via `rubric_path` (relative to the item directory). Global rubrics are not used.
- Prompts: the runner embeds the artifact and prompt template; required sections must be present in responses.
- Scoring: a deterministic rubric matches required statements and checks groundedness (referencing real IDs). Optional judge adds anchored, knowledge-aware scoring.
- Reports: results are written to `outputs/<run_id>/` and auto-rendered to `outputs/latest/report/index.html`.

**Pretraining/Overfitting Mitigations**
- Mandatory SPICE randomization: before prompting, the SPICE netlist is randomized per item/question and embedded in the prompt.
  - Shuffles device/source statement order while preserving `.model/.param/.control` headers and `.SUBCKT … .ENDS` blocks; continuation lines are kept with their device.
  - Jitters sizes within safe bounds: MOS `W` ×[0.85, 1.15], `L` ×[0.95, 1.05]; capacitors ×[0.7, 1.3]. Units are preserved.
  - Connectivity and topology are unchanged; instance/net names remain stable for groundedness.
  - Deterministic per-item seeds: derived from `meta.gen_seed` or a stable hash; the seed used is recorded in results as `artifact_randomization.seed`.
- Topology identification required: prompts include a mandatory `Topology` section; rubrics require correct topology identification scoped to that section (prevents accidental credit elsewhere in the answer).
- Groundedness checks: answers must cite real inventory IDs; hallucinated IDs incur penalties.

**Reproducibility**
- Runs are deterministic given the dataset and seeds. Randomization uses per-item seeds derived from `meta.json` (or a stable hash fallback) and is logged with each result.

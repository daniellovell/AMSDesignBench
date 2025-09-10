AMS Oral Knowledge LLM Bench
=================================

Qualitative, symbolic, and grounded benchmark for analog/mixed-signal IC design. Models read artifacts (image/netlist/Verilog-A/ADL), reason symbolically, and propose improvements. v0 avoids SPICE; scoring is rubric-based with groundedness checks.

Quick start
- Create a Python 3.10+ venv and install `requirements.txt`.
- Single model: `python harness/run_eval.py --model dummy --split dev`.
- Multiple models: `python harness/run_eval.py --models dummy openai:gpt-4o-mini --split dev`.
  - Also supported: comma-separated via `--model openai:gpt-4o-mini,dummy`.
  - Or set in `bench_config.yaml` under `eval.models: ["dummy", "openai:gpt-4o-mini"]` and run without `--model*` flags.
- Parallelism: multi-model runs execute in parallel by default. Control with `--model-workers N` (0 = run all models concurrently).
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
- `prompts/`: prompt templates per task family & modality.
- `rubrics/`: deterministic JSON rubrics.
- `knowledge/`: canonical fact sheets to anchor judging.
- `data/{train,dev,test}/<family>/<item_id>/`: artifacts + inventories + questions.
- `harness/`: adapters, scoring, reporting, runner.
- `scripts/`: item builder, audits, smoke test.

Design goals
- Symbolic, not numeric; grounded by inventory; rubric-based scoring; multimodal parity across image, SPICE, Verilog-A, ADL (no simulator needed).

Notes
- Minimal dataset: this repo currently includes only the OTA gain–bandwidth task (gbw_one_stage) to focus on infrastructure; other tasks have been removed.
- v0 uses deterministic rubric scoring + groundedness/hallucination checks. Optional LLM judge is stubbed and disabled by default.

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

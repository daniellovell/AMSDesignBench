AMS Oral Knowledge LLM Bench
=================================

Qualitative, symbolic, and grounded benchmark for analog/mixed-signal IC design. Models read artifacts (image/netlist/Verilog-A/ADL), reason symbolically, and propose improvements. v0 avoids SPICE; scoring is rubric-based with groundedness checks.

Quick start
- Create a Python 3.10+ venv and install `requirements.txt`.
- Run: `python harness/run_eval.py --model dummy --split dev`.
- Summarize: `python harness/reporting/summarize.py outputs/latest/results.jsonl`.

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
- v0 uses deterministic rubric scoring + groundedness/hallucination checks. Optional LLM judge is stubbed and disabled by default.

OpenAI adapter and Judge
- Env vars: set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` (default `gpt-4o-mini`).
- Run with OpenAI: `python harness/run_eval.py --model openai --split dev`.
- Enable LLM judge: add `--use-judge` (optionally `--judge-model gpt-4o-mini`).
- Results include `judge.overall` and `raw_blended` (80% deterministic + 20% judge).

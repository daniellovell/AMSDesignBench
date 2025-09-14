# AMSDesignBench

**A benchmark for evaluating Large Language Models on qualitative, symbolic, and grounded reasoning in analog/mixed-signal integrated circuit design.**

---

## Abstract

The AMSDesignBench is a specialized benchmark designed to assess the capabilities of Large Language Models (LLMs) in the domain of analog and mixed-signal (AMS) integrated circuit design. Moving beyond numerical simulation, this benchmark evaluates models on their ability to perform qualitative and symbolic reasoning about circuit behavior. Models are presented with design artifacts, such as SPICE netlists, and are tasked with analyzing circuit properties, identifying topologies, and proposing design improvements.

Evaluation is conducted through rubric-based checks with knowledge-anchored judging by a separate LLM (i.e. LLM-as-judge). A key focus is on "groundedness"—the ability of a model to base its analysis on components and connections present in the provided artifacts, thereby penalizing hallucinated or irrelevant information. To mitigate the effects of pretraining, the benchmark incorporates several techniques, including on-the-fly randomization of netlist components. This repository provides the complete framework for running evaluations, scoring results, and generating detailed reports.

## Benchmark Design and Methodology

The design of this benchmark is centered on evaluating symbolic understanding of analog circuits, a task that mirrors the reasoning process of human designers.

### Task Formulation
Instead of focusing on numerical precision, tasks are designed to be symbolic and qualitative. Models are asked to analyze properties like Gain-Bandwidth Product (GBW), output resistance (`Rout`), and output voltage swing for various operational transconductance amplifier (OTA) topologies. The input to the model is a SPICE netlist, and the expected output is a structured analysis in natural language.

### Scoring and Evaluation
The scoring mechanism is designed to be robust and multifaceted:

1.  **Rubric-Based Scoring**: Each question is associated with a detailed rubric that specifies the required analytical points. The harness performs deterministic checks to see if the model's response correctly identifies key circuit characteristics and relationships.
2.  **Groundedness Verification**: A critical component of the evaluation is ensuring that the model's reasoning is grounded in the provided circuit. The system checks that device names and circuit elements mentioned in the response correspond to actual elements in the SPICE netlist. Hallucinated components are penalized.
3.  **LLM as a Judge**: To capture the nuances of qualitative analysis, a separate LLM (the "judge") scores the model's response against a knowledge anchor. These anchors are curated fact sheets describing canonical circuit behaviors. This provides a consistent and knowledge-aware assessment of the response's quality.

### Overfitting and Pretraining Mitigation
To prevent models from simply recalling solutions from their training data, we employ several mitigation strategies:

*   **SPICE Netlist Randomization**: Before being presented to a model, every SPICE netlist undergoes a mandatory randomization process. This includes shuffling the order of device statements and applying jitter to transistor sizes, all while preserving the core topology and connectivity. This ensures that the model must analyze the circuit from first principles on each run.
*   **Topology Identification**: Prompts explicitly require the model to identify the circuit topology in a designated section of its response, preventing accidental credit from scattered keywords.
*   **Groundedness Checks**: By penalizing hallucinated inventory IDs, we discourage models from providing generic, non-specific answers.

## Getting Started

### 1. Setup

First, create a Python 3.10+ virtual environment and install the required dependencies.

  ```bash
  python3 -m venv venv
  source venv/bin/activate  # On Windows: venv\Scripts\activate
  pip install -r requirements.txt
  ```

Next, configure the API keys for the LLM providers you wish to use. These should be set as environment variables.

| Provider    | Environment Variable | Required For                 |
| :---------- | :------------------- | :--------------------------- |
| OpenAI      | `OPENAI_API_KEY`     | OpenAI models and LLM Judge  |
| Anthropic   | `ANTHROPIC_API_KEY`  | Anthropic models             |
| OpenRouter  | `OPENROUTER_API_KEY` | Models via OpenRouter        |

### 2. Running an Evaluation

The main script for running evaluations is `harness/run_eval.py`. You can run a single model or multiple models in parallel.

*   **Single model run:**
    ```bash
    python3 -m harness.run_eval --model dummy --split dev
    ```

*   **Multi-model run:**
    ```bash
    python3 -m harness.run_eval --models dummy openai:gpt-4o-mini --split dev --model-workers 2
    ```

Models can also be specified in `bench_config.yaml` under the `eval.models` key.

| Argument          | Description                                                                    | Default    |
| :---------------- | :----------------------------------------------------------------------------- | :--------- |
| `--models`        | A space-separated list of models to evaluate (e.g., `dummy openai:gpt-4o-mini`). | `[]`       |
| `--model`         | A single model or comma-separated list of models to evaluate.                  | `dummy`    |
| `--split`         | The dataset split to use.                                                      | `dev`      |
| `--max-items`     | Limit the number of items to run for each model (useful for testing).          | `None`     |
| `--model-workers` | The number of models to run in parallel.                                       | `0` (all)  |
| `--item-workers`  | The number of items to process in parallel for each model.                     | `8`        |
| `--judge-model`   | The model to use for the LLM judge.                                            | `gpt-4o`   |

### 3. Viewing Results

All outputs are saved to a timestamped directory inside `outputs/`. A symbolic link `outputs/latest` always points to the most recent run.

At the end of each evaluation, a comprehensive HTML report is automatically generated. To view it, open `outputs/latest/report/index.html` in your browser.

You can also generate summaries or re-render the report manually:

*   **Summarize results for all models:**
    ```bash
    python3 -m harness.reporting.compare outputs/latest/combined_results.jsonl
    ```
*   **Re-render the HTML report:**
    ```bash
    python3 -m harness.reporting.render outputs/latest/combined_results.jsonl
    ```

## Repository Structure

The repository is organized as follows:

| Path                        | Description                                                                  |
| :-------------------------- | :--------------------------------------------------------------------------- |
| `harness/`                  | The core evaluation harness, including the runner, model adapters, and scoring logic. |
| `data/`                     | Contains the dataset, split into `dev`, `test`, and `train` sets.            |
| `data/`                     | Dataset root, split into `dev`, `test`, `train`. Each split contains families (e.g., `analysis/`, `debugging/`, `design/`) and a shared `templates/` tree.            |
| `prompts/`                  | Prompt templates used for generating model inputs.                           |
| `rubrics/`                  | Scoring rubrics associated with evaluation questions.                        |
| `knowledge/`                | Knowledge anchor documents used by the LLM judge for consistent scoring.     |
| `outputs/`                  | Default directory for evaluation results and reports.                        |
| `bench_config.yaml`         | Main configuration file for paths, limits, and default models.               |

## Reproducibility

Runs are designed to be deterministic. The randomization of SPICE netlists is controlled by per-item seeds, which are derived from `meta.json` and logged with each result. This ensures that evaluations can be reproduced consistently given the same dataset and configuration.

## Families and Templates

- Families: The harness supports multiple evaluation families under each split (e.g., `data/dev/analysis`, `data/dev/debugging`, `data/dev/design`). Family directories contain items (e.g., `ota/ota001/`) with family-specific `questions.jsonl`, `rubrics/`, and `refs.json`.
- Shared templates: Common circuit sources live under `data/<split>/templates/` (e.g., `data/dev/templates/ota/ota001/`). Place canonical artifacts there (`netlist.sp`, `inventory.json`, optionally `design.adl`, `veriloga.va`).
- Referencing templates:
  - In each item’s `meta.json`, set `"template_path": "../../templates/<family>/<item_id>"` (relative to the item directory).
  - In `questions.jsonl`, set `"artifact_path"` to the desired artifact in the template (e.g., `../../templates/ota/ota001/netlist.sp`). If omitted, the harness falls back to the local artifact filename.
  - The harness resolves inventory from the template if `template_path` is defined; otherwise it uses a local `inventory.json` if present.

This structure avoids duplication across families while keeping family-specific prompts, rubrics, and refs close to their items.

### Debugging family

- For items under `data/<split>/debugging/...`, the harness can programmatically inject faults into the template netlist.
- The initial fault type is a device polarity swap (NMOS↔PMOS). For each debugging question with `modality: "spice_netlist"`, the runner loads the template `netlist.sp` and deterministically flips the model of one randomly chosen MOS device (`nch`↔`pch` or `NMOS`↔`PMOS`).
- The injected `swapped_id`, `from_type`, and `to_type` are passed to the judge via `refs`, enabling rubric/LLM-as-judge to verify that the answer names the correct device and fix.

### Design family

- For items under `data/<split>/design/...`, prompts ask the model to synthesize a structure/netlist. No artifact is required; rubric checks focus on topology description and presence of a plausible SPICE-like netlist.

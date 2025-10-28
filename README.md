# AMSDesignBench

**A benchmark for evaluating Large Language Models on qualitative, symbolic, and grounded reasoning in analog/mixed-signal integrated circuit design.**

---

## Abstract

The AMSDesignBench is a specialized benchmark designed to assess the capabilities of Large Language Models (LLMs) in the domain of analog and mixed-signal (AMS) integrated circuit design. Moving beyond numerical simulation, this benchmark evaluates models on their ability to perform qualitative and symbolic reasoning about circuit behavior. Models are presented with design artifacts, such as SPICE netlists, and are tasked with analyzing circuit properties, identifying topologies, and proposing design improvements.

Evaluation is conducted through rubric-based checks judged by a separate LLM (i.e. LLM-as-judge). A key focus is on "groundedness"—the ability of a model to base its analysis on components and connections present in the provided artifacts, thereby penalizing hallucinated or irrelevant information. To mitigate the effects of pretraining, the benchmark incorporates several techniques, including on-the-fly randomization of netlist components. This repository provides the complete framework for running evaluations, scoring results, and generating detailed reports.

## Benchmark Design and Methodology

The design of this benchmark is centered on evaluating symbolic understanding of analog circuits, a task that mirrors the reasoning process of human designers.

### Task Formulation
Instead of focusing on numerical precision, tasks are designed to be symbolic and qualitative. Models are asked to analyze properties like Gain-Bandwidth Product (GBW), output resistance (`Rout`), and output voltage swing for various operational transconductance amplifier (OTA) topologies. The input to the model is a SPICE netlist, and the expected output is a structured analysis in natural language.

### Scoring and Evaluation
The scoring mechanism is designed to be robust and multifaceted:

1.  **Rubric-Based Scoring**: Each question is associated with a detailed rubric that specifies the required analytical points. The harness performs deterministic checks to see if the model's response correctly identifies key circuit characteristics and relationships.
2.  **Groundedness Verification**: A critical component of the evaluation is ensuring that the model's reasoning is grounded in the provided circuit. The system checks that device names and circuit elements mentioned in the response correspond to actual elements in the SPICE netlist. Hallucinated components are penalized.
3.  **LLM as a Judge**: To capture the nuances of qualitative analysis, a separate LLM (the "judge") scores the model's response against a Markdown rubric for the specific task.

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
| `--family`        | Limit to a specific evaluation family under `data/<split>` (`analysis`, `debugging`, `design`). | `None`     |
| `--item-index`    | 1-based item index within the selected scope (after family filter). `0` = all. | `0`        |
| `--judge-model`   | The model to use for the LLM judge.                                            | `gpt-4o`   |

### 3. Viewing Results

All outputs are saved to a timestamped directory inside `outputs/`. A symbolic link `outputs/latest` always points to the most recent run.

At the end of each evaluation, a comprehensive HTML report is automatically generated. To view it, open `outputs/latest/report/index.html` in your browser.

You can also generate summaries, plots, or re-render the report manually:

*   **Summarize results for all models:**
    ```bash
    python3 -m harness.reporting.compare outputs/latest/combined_results.jsonl
    
    # Generate plots (auto-detect latest results)
    python3 -m harness.reporting.plots
    ```
*   **Re-render the HTML report:**
    ```bash
    python3 -m harness.reporting.render outputs/latest/combined_results.jsonl

### Plots

- The plotting utility generates a judge-score heatmap and per-family grouped bar charts by model × modality.
- Default (auto-detect latest):

  python3 -m harness.reporting.plots

- Custom results path and output directory:

  python3 -m harness.reporting.plots outputs/run_20250101_120000/combined_results.jsonl --out-dir outputs/run_20250101_120000/plots

Notes:
- Plots are written next to the results under a `plots/` folder by default (e.g., `outputs/latest/plots`).
- Requires matplotlib and numpy: `pip install matplotlib numpy`.
- By default, windows are opened interactively (show). To suppress and only write files, pass `--silent`.

## Repository Structure

The repository is organized as follows:

| Path                        | Description                                                                  |
| :-------------------------- | :--------------------------------------------------------------------------- |
| `harness/`                  | The core evaluation harness, including the runner, model adapters, and scoring logic. |
| `data/`                     | Dataset root, split into `dev`, `test`, `train`. Each split contains families (e.g., `analysis/`, `debugging/`, `design/`) and a shared `templates/` tree.            |
| `prompts/`                  | Prompt templates used for generating model inputs.                           |
| `rubrics/`                  | Scoring rubrics associated with evaluation questions.                        |
| `judge_prompts/`           | Common judge prompt includes and templates used across families.             |
| `outputs/`                  | Default directory for evaluation results and reports.                        |
| `bench_config.yaml`         | Main configuration file for paths, limits, and default models.               |

## Reproducibility

Runs are designed to be deterministic. The randomization of SPICE netlists is controlled by per-item seeds, which are derived from `meta.json` and logged with each result. This ensures that evaluations can be reproduced consistently given the same dataset and configuration.

## Families and Templates

- Families: The harness supports multiple evaluation families under each split (e.g., `data/dev/analysis`, `data/dev/debugging`, `data/dev/design`). Family directories contain items (e.g., `ota/ota001/`) with family-specific `questions.yaml`, `rubrics/`, and `refs.json`.
- Shared templates: Common circuit sources live under `data/<split>/templates/` (e.g., `data/dev/templates/ota/ota001/`). Place canonical artifacts there (`netlist.sp`, `inventory.json`, optionally `veriloga.va`).
- Referencing templates:
  - In each item's `meta.json`, set `"template_path": "../../templates/<family>/<item_id>"` (relative to the item directory).
  - In `questions.yaml`, you can:
    - Omit `"artifact_path"` and the runner will infer the template directory (`meta.template_path` when provided, otherwise derived from the folder name—`analysis/ota/ota005` → `../../../templates/ota/ota005`) and append the canonical filenames per modality (e.g., `netlist.sp`, `netlist.cir`, `netlist.cas`).
    - Provide `"artifact_path"` as the template directory (e.g., `../../templates/ota/ota001`). For `modality: auto` (and also for explicit modalities), the runner appends the canonical filename for each modality, so casIR/cascode will correctly use `netlist.cir`/`netlist.cas`.
    - Provide a full path to a specific artifact (e.g., `../../templates/ota/ota001/netlist.sp`). For `modality: auto`, the runner will preserve the directory and substitute the filename per modality so expansions point to the correct artifacts.
    - You can omit `require_sections`; the loader reads the `Required sections` list from the referenced prompt template and falls back to `Answer` if none is present.
    - Keep `prompt_template`, `rubric_id`, and `rubric_path` explicit so prompts, scoring, and references stay unambiguous.
  - The harness resolves inventory from the template if `template_path` is defined; otherwise it uses a local `inventory.json` if present.

This structure avoids duplication across families while keeping family-specific prompts, rubrics, and refs close to their items.

### Modalities and auto-detection

- The runner expands questions with `modality: auto` into one question per available artifact found in the item directory or the template directory.
- Recognized artifacts and their modalities:
  - `netlist.sp` → `spice_netlist` (SPICE)
  - `netlist.cas` → `cascode` (ADL)
  - `netlist.cir` → `casIR` (intermediate representation)
  - `veriloga.va` → `veriloga`
  - (legacy ADL `.adl` no longer supported)
  
Prompt wording:
- For clarity, prompts replace `cascode` with “analog description language” (e.g., “From the analog description language artifact…”), to avoid conflating with the cascode circuit topology.
  
Examples:
- Run a single debugging item (e.g., `ota002`) only: `python -m harness.run_eval --split dev --family debugging --item-index 2`
- Run two OpenAI models on `analysis` family: `python -m harness.run_eval --split dev --family analysis --models openai:gpt-4o-mini openai:gpt-4o --model-workers 2`

### Inventory passed to judges

- `spice_netlist`: Judges receive an inventory derived from the item/template `inventory.json` (IDs, nets, and aliases). Grounding criteria apply and hallucination penalties may be used per rubric.
- `casIR`: The `.cir` artifact itself defines the inventory at evaluation time. The harness parses its nets and motif IDs (adds helpful aliases such as `Cload`/`CL` for capacitors) and provides that to judges and to groundedness scoring.
- `cascode`: No concrete inventory exists. The harness disables grounding-based rubric criteria and hallucination penalties for this modality so answers are not scored on citing element IDs. Judges receive an empty inventory and a rubric with grounding weights set to 0.
- You can also control the set via `meta.json` `modalities`, but auto-detection will include any additional recognized files present.

### Debugging family

- For items under `data/<split>/debugging/...`, the harness can programmatically inject faults into the template netlist.
- Fault type: device polarity swap (NMOS↔PMOS).
- SPICE: For `modality: "spice_netlist"`, the runner loads the template `netlist.sp` and flips one MOS device (`nch`↔`pch` or `NMOS`↔`PMOS`). Writes `netlist_bug.sp`.
- casIR: If a `.cir` exists in the template, a parallel question is auto-added. The runner flips one motif `type` containing NMOS/PMOS inside the JSON and writes `netlist_bug.cir`.
- cascode (ADL): If a `.cas` exists, a parallel question is auto-added. The runner flips one occurrence of `NMOS`↔`PMOS` in type tokens and writes `netlist_bug.cas`.
- The injected `swapped_id`, `from_type`, and `to_type` are included in `refs` for scoring and judging.

### Design family

- For items under `data/<split>/design/...`, prompts ask the model to synthesize a structure/netlist. No artifact is required; rubric checks focus on topology description and presence of a plausible netlist.
- When a design item uses `modality: auto` and declares a `template_path` in `meta.json`, the runner expands into all available modalities discovered in the template (SPICE, casIR, analog description language `.cas`).
- Modality-specific prompts:
  - SPICE (`spice_netlist`): `design_ota.txt` (SPICE-like fenced block).
  - casIR (`casIR`): `design_ota_casir.txt`, injects two examples from `templates/ota/ota003` and `ota006` and asks for casIR JSON.
  - Analog description language (`cascode`): `design_ota_cas.txt`, injects two examples from `templates/ota/ota003` and `ota006` and asks for `.cas` ADL.
- Judges receive per-modality answer keys from the template for structural comparison:
  - casIR: `netlist.cir` is passed via refs and also used to derive an inventory for grounding.
  - ADL (`cascode`): `netlist.cas` is passed via refs; grounding is disabled for this modality.

Design brief:
- Each design item must include a plain-text `design_brief.txt` in the item directory (e.g., `data/dev/design/ota/ota001/design_brief.txt`).
- The brief is injected at the top of the prompt and tells the model exactly what topology to design.
- If `design_brief.txt` is missing, the harness errors out to keep datasets explicit and avoid implicit assumptions.

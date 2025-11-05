# Signal Modality — Judge Rubric

{path:../../judge_prompts/analysis_common_prompt.md}

{path:feedback_common_instructions.md}

Scoring: compute `overall = {weight_signal_modality}*scores.signal_modality + {weight_grounded_evidence}*scores.grounded_evidence + {weight_format}*scores.format`.

## Criteria
- **signal_modality** — Credit explicit identification of the input/output modality defined in the Answer Key; partial credit for implied but incomplete statements.
- **format** — Penalize contradictory modality descriptions or incorrect classifications.
{path:feedback_common_criteria.md}

## Answer Key

### signal_modality
- Expected modality: `{signal_modality_target}`.
- Guidance: `{signal_modality_guidance}`.
- Reject statements: `{signal_modality_reject}`.

### grounded_evidence
- Allowed identifiers: Use `inventory.allowed_ids` from the CONTEXT JSON payload to determine which identifiers are valid.
- The inventory is provided in the CONTEXT section of the judge prompt as a JSON object with `allowed_ids` (list of valid identifiers) and `canonical_map` (mapping of aliases to canonical names).
- Minimum grounded references for scores >0.5: `{grounded_min_refs}`.
- Guidance: `{grounded_guidance}`. Deduct for identifiers not present in `inventory.allowed_ids`.

### format
- Reject statements: `{format_reject}`.
- Guidance: `{format_guidance}`.

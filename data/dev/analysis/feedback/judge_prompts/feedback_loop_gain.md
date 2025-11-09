# Loop Gain — Judge Rubric

{path:../../judge_prompts/analysis_common_prompt.md}

{path:feedback_common_instructions.md}

Scoring: compute the overall score as a weighted sum: `overall = {weight_loop_gain_expression}*scores.loop_gain_expression + {weight_grounded_evidence}*scores.grounded_evidence`. **IMPORTANT: Output the computed numeric result (e.g., 0.75) in the `overall` field, NOT the formula itself.**

## Criteria
- **loop_gain_expression** — Award credit when the answer states the loop gain described in the Answer Key without leaving symbolic placeholders undefined. Penalize confusion between loop gain and closed-loop gain or contradictions.
{path:feedback_common_criteria.md}

## Answer Key

### loop_gain_expression
- Accept loop gain forms: `{loop_gain_target}`.
- Disallow unresolved forms: `{loop_gain_disallowed}`.
- Guidance: `{loop_gain_guidance}`.
- Reject statements: `{loop_gain_reject}`.

### grounded_evidence
- Allowed identifiers: Use `inventory.allowed_ids` from the CONTEXT JSON payload to determine which identifiers are valid.
- The inventory is provided in the CONTEXT section of the judge prompt as a JSON object with `allowed_ids` (list of valid identifiers) and `canonical_map` (mapping of aliases to canonical names).
- Minimum grounded references for scores >0.5: `{grounded_min_refs}`.
- Guidance: `{grounded_guidance}`. Deduct for identifiers not present in `inventory.allowed_ids`.

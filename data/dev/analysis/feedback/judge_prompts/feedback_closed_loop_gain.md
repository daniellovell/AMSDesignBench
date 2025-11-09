# Closed-Loop Gain — Judge Rubric

{path:../../judge_prompts/analysis_common_prompt.md}

{path:feedback_common_instructions.md}

Scoring: compute the overall score as a weighted sum: `overall = {weight_gain_expression}*scores.gain_expression + {weight_grounded_evidence}*scores.grounded_evidence`. **IMPORTANT: Output the computed numeric result (e.g., 0.75) in the `overall` field, NOT the formula itself.**

## Criteria
- **gain_expression** — Award credit when the answer states the closed-loop gain described in the Answer Key; partial credit if conceptually correct but incomplete. Penalize incorrect signs, inconsistent dependencies, or contradictions.
{path:feedback_common_criteria.md}

## Answer Key

### gain_expression
- Expected statement: `{gain_expression_target}`.
- Guidance: `{gain_expression_guidance}`.
- Reject variants: `{gain_expression_reject}`.

### grounded_evidence
- Allowed identifiers: Use `inventory.allowed_ids` from the CONTEXT JSON payload to determine which identifiers are valid.
- The inventory is provided in the CONTEXT section of the judge prompt as a JSON object with `allowed_ids` (list of valid identifiers) and `canonical_map` (mapping of aliases to canonical names).
- Minimum grounded references for scores >0.5: `{grounded_min_refs}`.
- Guidance: `{grounded_guidance}`. Deduct for identifiers not present in `inventory.allowed_ids`.

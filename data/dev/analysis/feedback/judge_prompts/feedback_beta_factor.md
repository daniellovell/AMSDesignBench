# Feedback Beta Factor — Judge Rubric

{path:../../judge_prompts/analysis_common_prompt.md}

{path:feedback_common_instructions.md}

Scoring: compute the overall score as a weighted sum: `overall = {weight_beta_expression}*scores.beta_expression + {weight_grounded_evidence}*scores.grounded_evidence`. **IMPORTANT: Output the computed numeric result (e.g., 0.75) in the `overall` field, NOT the formula itself.**

## Criteria
- **beta_expression** — Award credit when the answer states the feedback factor described in the Answer Key; allow partial credit for conceptually correct but imprecise wording. Penalize contradictions or incorrect beta statements.

{path:feedback_common_criteria.md}

## Answer Key

### beta_expression
- Target statement: `{beta_expression_target}`.
- Additional guidance: `{beta_expression_guidance}`.
- Reject variants: `{beta_expression_reject}`.

### grounded_evidence
- Allowed identifiers: Use `inventory.allowed_ids` from the CONTEXT JSON payload to determine which identifiers are valid.
- The inventory is provided in the CONTEXT section of the judge prompt as a JSON object with `allowed_ids` (list of valid identifiers) and `canonical_map` (mapping of aliases to canonical names).
- Minimum grounded references for scores >0.5: `{grounded_min_refs}`.
- Guidance: `{grounded_guidance}`. Deduct for identifiers not present in `inventory.allowed_ids`.

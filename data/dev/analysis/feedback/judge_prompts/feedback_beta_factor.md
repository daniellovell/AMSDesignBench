# Feedback Beta Factor — Judge Rubric

{path:../../judge_prompts/analysis_common_prompt.md}

{path:feedback_common_instructions.md}

Scoring: compute `overall = {weight_beta_expression}*scores.beta_expression + {weight_grounded_evidence}*scores.grounded_evidence`.

## Criteria
- **beta_expression** — Award credit when the answer states the feedback factor described in the Answer Key; allow partial credit for conceptually correct but imprecise wording. Penalize contradictions or incorrect beta statements.

{path:feedback_common_criteria.md}

## Answer Key

### beta_expression
- Target statement: `{beta_expression_target}`.
- Additional guidance: `{beta_expression_guidance}`.
- Reject variants: `{beta_expression_reject}`.

### grounded_evidence
- Allowed identifiers: `{grounded_allowed_ids}`.
- Minimum grounded references for scores >0.5: `{grounded_min_refs}`.
- Guidance: `{grounded_guidance}`.

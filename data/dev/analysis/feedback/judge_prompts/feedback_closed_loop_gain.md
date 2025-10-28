# Closed-Loop Gain — Judge Rubric

{path:../../judge_prompts/analysis_common_prompt.md}

{path:feedback_common_instructions.md}

Scoring: compute `overall = {weight_gain_expression}*scores.gain_expression + {weight_grounded_evidence}*scores.grounded_evidence`.

## Criteria
- **gain_expression** — Award credit when the answer states the closed-loop gain described in the Answer Key; partial credit if conceptually correct but incomplete. Penalize incorrect signs, inconsistent dependencies, or contradictions.
{path:feedback_common_criteria.md}

## Answer Key

### gain_expression
- Expected statement: `{gain_expression_target}`.
- Guidance: `{gain_expression_guidance}`.
- Reject variants: `{gain_expression_reject}`.

### grounded_evidence
- Allowed identifiers: `{grounded_allowed_ids}`.
- Minimum grounded references for scores >0.5: `{grounded_min_refs}`.
- Guidance: `{grounded_guidance}`.

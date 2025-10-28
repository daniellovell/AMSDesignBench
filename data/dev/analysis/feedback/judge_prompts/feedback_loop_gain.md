# Loop Gain — Judge Rubric

{path:../../judge_prompts/analysis_common_prompt.md}

{path:feedback_common_instructions.md}

Scoring: compute `overall = {weight_loop_gain_expression}*scores.loop_gain_expression + {weight_grounded_evidence}*scores.grounded_evidence + {weight_correctness}*scores.correctness`.

## Criteria
- **loop_gain_expression** — Award credit when the answer states the loop gain described in the Answer Key without leaving symbolic placeholders undefined.
- **correctness** — Penalize confusion between loop gain and closed-loop gain or contradictions.
{path:feedback_common_criteria.md}

## Answer Key

### loop_gain_expression
- Accept loop gain forms: `{loop_gain_target}`.
- Disallow unresolved forms: `{loop_gain_disallowed}`.
- Guidance: `{loop_gain_guidance}`.
- Reject statements: `{loop_gain_reject}`.

### grounded_evidence
- Allowed identifiers: `{grounded_allowed_ids}`.
- Minimum grounded references for scores >0.5: `{grounded_min_refs}`.
- Guidance: `{grounded_guidance}`.

### correctness
- Reject statements: `{correctness_reject}`.
- Guidance: `{correctness_guidance}`.

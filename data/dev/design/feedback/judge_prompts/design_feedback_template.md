# Feedback Design — Judge Rubric

{path:../../judge_prompts/design_common_prompt.md}

{path:../../judge_prompts/design_feedback_common_instructions.md}

Scoring: compute the overall score as a weighted sum: `overall = {weight_structural_correctness}*scores.structural_correctness + {weight_topology_terms}*scores.topology_terms + {weight_safety}*scores.safety`. **IMPORTANT: Output the computed numeric result (e.g., 0.75) in the `overall` field, NOT the formula itself.**

## Criteria

{path:../../judge_prompts/design_feedback_common_criteria.md}

## Answer Key

### structural_correctness
- Guidance: `{structural_correctness_guidance}`.

### topology_terms
- Required patterns (any `{topology_min_any}`): `{topology_patterns_any}`.

### safety
- Reject patterns: `{safety_anti_patterns}`.
- Hallucination penalty: `{hallucination_penalty}` per invalid element reference.

---

**Scoring Summary:**
- Minimum passing score: `{min_pass}`.


# Identify Transfer Function — Judge Rubric

{path:../../judge_prompts/analysis_common_prompt.md}{path:filters_common_instructions.md}

Scoring: Compute `overall` as the weighted sum: {weight_topology}*scores.topology + {weight_tf}*scores.tf + {weight_grounded_evidence}*scores.grounded_evidence

## Criteria
- **tf** — Award credit for the correct symbolic H(s) form; accept algebraically equivalent forms.
{path:filters_common_criteria.md}

## Answer Key

### topology
- Target: {topology_target}.
- Reject variants: {topology_rejects}.

### tf
- Target: {tf_target}.
- Acceptable equivalents: {tf_equivalents}.

### grounded_evidence
- Allowed identifiers: Use `inventory.allowed_ids` from the CONTEXT JSON payload to determine which identifiers are valid.
- The inventory is provided in the CONTEXT section of the judge prompt as a JSON object with `allowed_ids` (list of valid identifiers) and `canonical_map` (mapping of aliases to canonical names).
- Minimum grounded references (>0.5 score): {grounded_min_refs}.
- Guidance: {grounded_guidance}. Award credit for valid citations from `inventory.allowed_ids`. Deduct for identifiers not present in `inventory.allowed_ids` (hallucinated elements).


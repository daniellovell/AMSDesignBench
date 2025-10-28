# Identify Transfer Function — Judge Rubric

{path:../../judge_prompts/analysis_common_prompt.md}{path:filters_common_instructions.md}

Scoring: overall = {weight_topology}*scores.topology + {weight_tf}*scores.tf + {weight_grounded_evidence}*scores.grounded_evidence + {weight_safety}*scores.safety

## Criteria
- topology — Award credit when the answer names the correct filter type/order in a Topology section; allow close variants.
- tf — Award credit for the correct symbolic H(s) form; accept algebraically equivalent forms.
- grounded_evidence — Require grounded citations; deduct for unsupported claims or disallowed identifiers.
- safety — Penalize hallucinated elements/nets not present in inventory.

{path:filters_common_criteria.md}

## Answer Key

### topology
- Target: {topology_target}.
- Reject variants: {topology_rejects}.

### tf
- Target: {tf_target}.
- Acceptable equivalents: {tf_equivalents}.

### grounded_evidence
- Allowed identifiers: {grounded_allowed_ids}.
- Minimum grounded references (>0.5 score): {grounded_min_refs}.
- Guidance: {grounded_guidance}.

### safety
- Guidance: {safety_guidance}.


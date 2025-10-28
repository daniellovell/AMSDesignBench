# Quiescent Power — Judge Rubric

{path:../../judge_prompts/analysis_common_prompt.md}{path:ota_common_instructions.md}

Scoring: overall = {weight_topology}*scores.topology + {weight_key_relation}*scores.key_relation + {weight_device_specificity}*scores.device_specificity + {weight_grounded_evidence}*scores.grounded_evidence + {weight_safety}*scores.safety

## Criteria
- topology — Identify the OTA topology; allow close variants.
- key_relation — State the requested canonical relation; accept algebraically equivalent forms.
- device_specificity — Use device-specific symbols where applicable.
- grounded_evidence — Require grounded citations; deduct for disallowed identifiers.
- safety — Penalize hallucinated elements.

{path:ota_common_criteria.md}

## Answer Key

### topology
- Target: {topology_target}.
- Reject variants: {topology_rejects}.

### key_relation
- Target: {relation_target}.
- Acceptable equivalents: {relation_equivalents}.

### device_specificity
- Guidance: {device_guidance}.

### grounded_evidence
- Allowed identifiers: {grounded_allowed_ids}.
- Minimum grounded references (>0.5 score): {grounded_min_refs}.
- Guidance: {grounded_guidance}.

### safety
- Guidance: {safety_guidance}.

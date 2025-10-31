{path:../../judge_prompts/analysis_common_prompt.md}
{path:ota_common_instructions.md}

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
- Guidance: Use gm_Mi, ro_Mj (or equivalent) where applicable.

### grounded_evidence
- Allowed identifiers: Use `inventory.allowed_ids` from the CONTEXT JSON payload to determine which identifiers are valid.
- The inventory is provided in the CONTEXT section of the judge prompt as a JSON object with `allowed_ids` (list of valid identifiers) and `canonical_map` (mapping of aliases to canonical names).
- Minimum grounded references (>0.5 score): 3.
- Guidance: Cite actual device IDs/nets from inventory to support claims. Deduct for identifiers not present in `inventory.allowed_ids`.

### safety
- Guidance: Do not invent devices or nets not present in inventory. Check against `inventory.allowed_ids` from the CONTEXT JSON payload.

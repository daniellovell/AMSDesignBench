{path:../../judge_prompts/analysis_common_prompt.md}
{path:ota_common_instructions.md}

Scoring: overall = {weight_topology}*scores.topology + {weight_key_relation}*scores.key_relation + {weight_device_specificity}*scores.device_specificity + {weight_grounded_evidence}*scores.grounded_evidence + {weight_safety}*scores.safety

{path:ota_common_criteria.md}

## Answer Key

### topology
- Target: {topology_target}.
- Reject variants: {topology_rejects}.

### key_relation
- Target: {relation_target}.
- Acceptable equivalents: {relation_equivalents}.

### device_specificity
- Target: Use device-specific symbols (e.g., gm_Mi, ro_Mj) where applicable.
- Guidance: Acceptable formats include gm_M1, ro_M2, or equivalent notation. Avoid generic symbols (e.g., gm, ro) when device-specific identification is required.

### grounded_evidence
- Target: Cite actual device IDs/nets from inventory to support claims.
- Minimum grounded references (>0.5 score): 3.
- Allowed identifiers: Use `inventory.allowed_ids` from the CONTEXT JSON payload to determine which identifiers are valid.
- The inventory is provided in the CONTEXT section of the judge prompt as a JSON object with `allowed_ids` (list of valid identifiers) and `canonical_map` (mapping of aliases to canonical names).
- Guidance: Deduct for identifiers not present in `inventory.allowed_ids`.

### safety
- Target: No hallucinated elements; all referenced devices/nets must exist in inventory.
- Guidance: Check against `inventory.allowed_ids` from the CONTEXT JSON payload. Do not invent devices or nets not present in inventory.

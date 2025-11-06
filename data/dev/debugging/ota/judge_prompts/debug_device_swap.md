# Device Swap Debug — Judge Rubric

{path:../../judge_prompts/debugging_common_prompt.md}

{path:../../judge_prompts/debug_common_instructions.md}

Scoring: compute `overall = {weight_fault_id}*scores.fault_id + {weight_fix}*scores.fix + {weight_grounding}*scores.grounding + {weight_safety}*scores.safety`.

## Criteria

- **fault_id** — Award credit when the answer correctly identifies the device with swapped polarity matching {runtime:swapped_id}, {runtime:from_type}, {runtime:to_type}. Check for mentions of PMOS/NMOS swap or wrong device type. Full credit requires citing the specific device ID and type mismatch. Partial credit for generic fault identification. Guidance: {fault_id_guidance}.

- **fix** — Award credit when a concrete fix is proposed: change device model to correct type (e.g., nch/pch) and specify correct body connection (0/VDD). Partial credit for incomplete fixes. Guidance: {fix_guidance}.

{path:../../judge_prompts/debug_common_criteria.md}

## Answer Key

### fault_id
- Section: `{fault_id_section}`.
- Required patterns (any {fault_id_min_any}): `{fault_id_patterns_any}`.
- Reject patterns: `{fault_id_anti_patterns}`.
- Match against {runtime:swapped_id}, {runtime:from_type}, {runtime:to_type} from the rubric.

### fix
- Section: `{fix_section}`.
- Expected patterns (any {fix_min_any}): `{fix_patterns_any}`.

### grounding
- Minimum grounded references: `{grounded_min_refs}`.
- Guidance: `{grounded_guidance}`.

### safety
- Hallucination penalty: `{hallucination_penalty}` per invalid element reference.
- Guidance: `{safety_guidance}`.

---

**Scoring Summary:**
- Minimum passing score: `{min_pass}`.
- Overall = weighted sum of criterion scores.

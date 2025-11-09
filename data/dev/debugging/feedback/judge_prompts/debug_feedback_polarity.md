# Feedback Polarity Debug — Judge Rubric

{path:../../judge_prompts/debugging_common_prompt.md}

{path:../../judge_prompts/debug_common_instructions.md}

Scoring: compute the overall score as a weighted sum: `overall = {weight_fault_identification}*scores.fault_identification + {weight_grounded_evidence}*scores.grounded_evidence + {weight_fix}*scores.fix + {weight_clarity}*scores.clarity`. **IMPORTANT: Output the computed numeric result (e.g., 0.45) in the `overall` field, NOT the formula itself.**

## Criteria

- **fault_identification** — Award credit when the answer correctly identifies the feedback polarity issue (positive vs negative feedback) and states whether it is correct for the circuit. Full credit requires explicit statement of the problem (e.g., "circuit has positive feedback but needs negative feedback"). Guidance: {fault_identification_guidance}.

- **fix** — Award credit when a concrete fix is proposed to establish proper negative feedback (e.g., "swap opamp inverting and non-inverting inputs" or "reconnect resistor from output to inverting input"). Partial credit for vague fixes. Guidance: {fix_guidance}.

- **clarity** — Award credit for clear explanation of symptoms caused by incorrect feedback polarity (instability, oscillation, saturation) and expected correct behavior. Guidance: {clarity_guidance}.

{path:../../judge_prompts/debug_common_criteria.md}

## Answer Key

### fault_identification
- Section: `{fault_identification_section}`.
- Check rubric answer key for expected polarity issue (bug_type: {bug_type}, expected_feedback: {expected_feedback}, actual_feedback: {actual_feedback}).

### grounded_evidence
- Section: `{grounded_evidence_section}`.
- Minimum grounded references: `{grounded_min_refs}`.
- Guidance: `{grounded_evidence_guidance}`.

### fix
- Section: `{fix_section}`.
- Guidance: `{fix_guidance}`.

### clarity
- Section: `{clarity_section}`.
- Guidance: `{clarity_guidance}`.

---

**Scoring Summary:**
- Minimum passing score: `{min_pass}`.
- Hallucination penalty: `{hallucination_penalty}` per invalid element reference.

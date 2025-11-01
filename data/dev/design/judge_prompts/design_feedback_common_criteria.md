- **structural_correctness**: Award credit when the feedback network and op‑amp connections match the intended configuration (e.g., TIA resistor/capacitor, inverting/noninverting), aligned with the modality answer key in refs when present. Partial credit for capturing most connections.

- **topology_terms**: Award credit when correct configuration terms are used. Require at least `{topology_min_any}` matched terms from `{topology_patterns_any}` for scores above 0.5.

- **safety**: Penalize explicit anti‑patterns from `{safety_anti_patterns}`. Also deduct `{hallucination_penalty}` per asserted element identifier not present in `inventory.allowed_ids` (ignore this penalty if `inventory.grounding_disabled` is true).


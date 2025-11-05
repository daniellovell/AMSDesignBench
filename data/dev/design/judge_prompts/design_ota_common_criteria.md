- **structural_correctness**: Award credit when the described netlist structure matches the intended topology for the given modality (SPICE/casIR/ADL), including the signal path, load, bias devices, and output configuration. Accept canonicalized aliasing per `inventory.canonical_map`. Partial credit for capturing major structural features while missing some details.

- **topology_terms**: Award credit when the answer uses correct topology terminology. Require at least `{topology_min_any}` matched terms from `{topology_patterns_any}` for scores above 0.5. Penalize unrelated or contradictory claims.

- **safety**: Penalize explicit anti‑patterns from `{safety_anti_patterns}`. Also deduct `{hallucination_penalty}` per asserted element identifier that is not in `inventory.allowed_ids` (ignore this hallucination penalty if `inventory.grounding_disabled` is true).


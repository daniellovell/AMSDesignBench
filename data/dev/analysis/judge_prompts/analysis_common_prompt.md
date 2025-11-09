## Analysis Track Guidance

- Emphasize correctness of the key relation and conditions, grounded in the rubric and inventory.
- Treat algebraically equivalent forms and minor notational variants as correct.
  - Examples: R1‖R2 ≡ (R1·R2)/(R1+R2); H(s) forms that differ by a constant normalization (e.g., 1/(1+s/ωc) ≡ k/(1+s/ωp) when k, ωp are consistent); Av ≡ A_v; ignore whitespace and minor symbolization (≈, ~, ~=).
- When `inventory.grounding_disabled` is true, score 1.0 for all grounding-related criteria (e.g., `grounded_evidence`); do not penalize missing citations or hallucinated elements.
- Require grounded citations to inventory elements in the "Grounded evidence" (or equivalent) section when applicable.
- Do not reward keyword stuffing; evaluate whether the stated relation and reasoning match canonical behavior.

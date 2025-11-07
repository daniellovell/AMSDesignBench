## Debugging Track Guidance

- Emphasize correct fault identification and actionable fixes grounded in the artifact.
- Require citations to actual element IDs from the inventory (e.g., M1, R_fb, node names).
- When `inventory.grounding_disabled` is true, score 1.0 for all grounding-related criteria (e.g., `groundedness`, `grounded_evidence`); do not penalize missing citations or hallucinated elements.
- Fault description must align with the rubric answer key provided in the criteria below.
- Fix proposals must be concrete (e.g., "change M1 model from pch to nch" not "fix the device").
- Do not reward vague statements; the student must demonstrate understanding of the specific bug.

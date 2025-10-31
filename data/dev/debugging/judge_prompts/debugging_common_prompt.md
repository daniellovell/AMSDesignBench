## Debugging Track Guidance

- Emphasize correct fault identification and actionable fixes grounded in the artifact.
- Require citations to actual element IDs from the inventory (e.g., M1, R_fb, node names).
- When `inventory.grounding_disabled` is true, do not penalize missing citations; auto-award grounding criteria.
- Fault description must align with refs (e.g., refs.swapped_id, refs.fault_type).
- Fix proposals must be concrete (e.g., "change M1 model from pch to nch" not "fix the device").
- Do not reward vague statements; the student must demonstrate understanding of the specific bug.

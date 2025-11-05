## Design Track Guidance

- Emphasize structural correctness of the topology and clear use of standard terminology; ground judgments in the rubric and the provided inventory summary.
- Treat reasonable naming variants and canonicalized aliases as equivalent when `inventory.canonical_map` indicates so (e.g., single‑ended ≡ single end; vout ≡ vop when canonicalized).
- For modality‑specific answer keys (e.g., `{modmux:answer_key}`), prefer checking consistency with the expected connectivity and block structure rather than literal formatting.
- When `inventory.grounding_disabled` is true, do not penalize citation‑style issues; apply only anti‑pattern checks under safety and ignore hallucination penalties.
- Do not reward keyword stuffing; the explanation must match the intended structure/topology and avoid contradictions.


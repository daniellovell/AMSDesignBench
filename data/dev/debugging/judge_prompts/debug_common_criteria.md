- **groundedness** / **grounded_evidence**: Award only when the explanation cites allowed element IDs from `inventory.allowed_ids` in the CONTEXT JSON payload. Require at least `{grounded_min_refs}` distinct citations for scores above 0.5. Do not award for generic language lacking specific element references.

- **safety**: Penalize hallucinated element IDs not present in `inventory.allowed_ids`. Award full credit if no hallucinations detected; deduct proportionally for each invalid reference.

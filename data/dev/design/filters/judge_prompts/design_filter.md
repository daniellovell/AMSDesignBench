# Filter Design — Judge Rubric

{path:../../judge_prompts/design_common_prompt.md}

Scoring: compute the overall score as a weighted sum: `overall = 0.2*scores.has_spice_netlist + 0.3*scores.has_components + 0.2*scores.has_input_output + 0.3*scores.reasonable_values`. **IMPORTANT: Output the computed numeric result (e.g., 0.75) in the `overall` field, NOT the formula itself.**

## Criteria

- **has_spice_netlist**: Response includes a SPICE netlist. Required. Match any of these patterns: `` ```spice ``, ``Vin``, ``vout``.

- **has_components**: Design includes appropriate components. Required. Match any of these patterns: `^[RCL][0-9], Vin`.

- **has_input_output**: Design specifies input and output nodes. Required. Match any of these patterns: `vin, vout`.

- **correct_values**: Component values are specified, and correct according to the filter design equation {filter_design_equation}.

---

**Scoring Summary:**
- Minimum passing score: `0.6`.


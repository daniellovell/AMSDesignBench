Filters Family (templates)

This folder contains SPICE templates for the `filters` family used as artifacts in the LLM bench. Netlists intentionally avoid descriptive comments and may use `?` for component values so models must infer topology and derive symbolic transfer functions from structure alone.

Summary

| Filter ID | Filter Type | Transfer Function (Answer Key) | Filter Class |
|-----------|-------------|--------------------------------|--------------|
| filter001 | First‑order RC network | $H(s) = \frac{1}{1 + s}$ (normalized low-pass) | Low-Pass |
| filter002 | First‑order CR network | $H(s) = \frac{s}{1 + s}$ (normalized high-pass) | High-Pass |
| filter003 | Series RL feeding a shunt R | $H(s) = \frac{R}{R + sL}$ | Low-Pass |
| filter004 | Passive R–L–C network | $H(s) = \frac{s}{s^2 + s/Q + 1}$ (normalized band-pass) | Band-Pass |
| filter005 | Two cascaded active biquads | $H(s) = \frac{1}{s^2 + s/Q_1 + 1} \cdot \frac{1}{s^2 + s/Q_2 + 1}$ | 4th-Order Low-Pass |
| filter006 | Two cascaded active biquads (ind. tunings) | $H(s) = \frac{1}{s^2 + s/Q_1 + 1} \cdot \frac{1}{s^2 + s/Q_2 + 1}$ | 4th-Order Low-Pass |
| filter007 | RL low‑pass (series L, shunt R) | $H(s) = \frac{R}{R + sL}$ | Low-Pass |
| filter008 | First‑order all‑pass (op‑amp) | $H(s) = \frac{1 - s}{1 + s}$ (normalized all-pass) | All-Pass |
| filter009 | Passive twin‑T notch | $H(s) = \frac{s^2 + 1}{s^2 + s/Q + 1}$ (normalized notch) | Band-Stop (Notch) |
| filter010 | Second‑order high‑pass | $H(s) = \frac{s^2}{s^2 + s/Q + 1}$ (normalized high-pass) | High-Pass |
| filter011 | Active band‑pass (MFB) | $H(s) = \frac{H_0(s/\omega_0)}{(s/\omega_0)^2 + (s/\omega_0)/Q + 1}$ | Band-Pass |
| filter012 | State‑variable biquad (BP output) | $H(s) = \frac{(\omega_0/Q)s}{s^2 + (\omega_0/Q)s + \omega_0^2}$ | Band-Pass |

**Notation:**
- Transfer functions shown are the expected answer keys for analysis questions
- Most are given in normalized form (ω₀ = 1) unless specified otherwise
- $s$ — complex frequency variable (Laplace domain)
- $\omega_0$ — natural/center frequency
- $Q$ — quality factor
- $H_0$ — midband/passband gain

Analysis Questions

Each filter topology is evaluated with a transfer function identification question (track: `analysis`):

| Question Aspect | Description | Evaluation Criteria |
|----------------|-------------|---------------------|
| **Transfer Function Identification** | Derive the symbolic transfer function $H(s) = V_{out}(s)/V_{in}(s)$ from circuit structure | 35% topology recognition, 35% correct TF form, 30% grounded evidence (cite ≥2 components) |

**Expected response**: Models must analyze the circuit structure, identify key components (R, L, C, op-amp), apply circuit analysis techniques (voltage dividers, KCL/KVL, op-amp golden rules), and derive the transfer function in symbolic form. The answer should be expressed in standard normalized form where applicable.

**Common normalizations**:
- First-order: $\omega_c = 1/(RC)$ or $R/L$ → normalize to $H(s) = \ldots/(1 + s)$
- Second-order: $\omega_0 = 1/\sqrt{LC}$, $Q$ defined by damping → normalize using $(s/\omega_0)$

Debugging Questions

No debugging questions are currently defined for the filters family.

Notes

- Op‑amp is referenced as a subcircuit `OPAMP` and is not defined in these templates.
- Values marked `?` are intentionally unspecified for symbolic reasoning tasks and may not simulate as‑is.

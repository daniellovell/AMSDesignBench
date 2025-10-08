Filters Family (templates)

This folder contains SPICE templates for the `filters` family used as artifacts in the LLM bench. Netlists intentionally avoid descriptive comments and may use `?` for component values so models must infer topology and derive symbolic transfer functions from structure alone.

Summary

| Filter ID | Filter Type | Transfer Function |
|-----------|-------------|-------------------|
| filter001 | First‑order RC network | $H(s) = \frac{1}{1 + sRC}$ |
| filter002 | First‑order CR network | $H(s) = \frac{sRC}{1 + sRC}$ |
| filter003 | Series RL feeding a shunt R (output across R) | $H(s) = \frac{R}{R + sL}$ |
| filter004 | Passive R–L–C network (band‑pass) | $H(s) = \frac{s/\omega_0}{(s/\omega_0)^2 + s/(Q\omega_0) + 1}$ |
| filter005 | Two cascaded active biquads (generic low‑pass) | $H(s) = \frac{1}{s^2/\omega_1^2 + s/(Q_1\omega_1) + 1} \cdot \frac{1}{s^2/\omega_2^2 + s/(Q_2\omega_2) + 1}$ |
| filter006 | Two cascaded active biquads (independent tunings) | Same product form as filter005 with $(\omega_k, Q_k)$ per design |
| filter007 | RL low‑pass (series L, shunt R; Vout across R) | $H(s) = \frac{R}{R + sL}$ |
| filter008 | First‑order all‑pass (op‑amp) | $H(s) = \frac{1 - sRC}{1 + sRC}$ |
| filter009 | Passive twin‑T notch (band‑stop) | $H(s) = \frac{s^2 + \omega_0^2}{s^2 + (\omega_0/Q)s + \omega_0^2}$ |
| filter010 | Second‑order high‑pass (two‑pole) | $H(s) = \frac{Ks^2}{s^2 + (\omega_0/Q)s + \omega_0^2}$ |
| filter011 | Active band‑pass (one‑op‑amp, MFB) | $H(s) = \frac{H_0(s/\omega_0)}{(s/\omega_0)^2 + (s/\omega_0)/Q + 1}$ |
| filter012 | State‑variable biquad (BP output) | $H(s) = \frac{(\omega_0/Q)s}{s^2 + (\omega_0/Q)s + \omega_0^2}$ |

Notes

- Op‑amp is referenced as a subcircuit `OPAMP` and is not defined in these templates.
- Values marked `?` are intentionally unspecified for symbolic reasoning tasks and may not simulate as‑is.

Filters Family (templates)

This folder contains SPICE templates for the `filters` family used as artifacts in the LLM bench. Netlists intentionally avoid descriptive comments and may use `?` for component values so models must infer topology and derive symbolic transfer functions from structure alone.

Summary

- filter001 — First‑order RC network
  - Example form: H(s) = 1 / (1 + s R C)
- filter002 — First‑order CR network
  - Example form: H(s) = s R C / (1 + s R C)
- filter003 — Series RL feeding a shunt R (output across R)
  - Example form: H(s) = R / (R + s L)
- filter004 — Passive R–L–C network with a single resonant pole pair
  - Normalized band‑pass form: H(s) = (s/ω0) / ((s/ω0)^2 + (s/(Q ω0)) + 1)
- filter005 — Two cascaded active biquads (op‑amp based)
  - Section form (generic low‑pass biquad): H(s) = 1 / (s^2/(ω1^2) + s/(Q1 ω1) + 1) · 1 / (s^2/(ω2^2) + s/(Q2 ω2) + 1)
- filter006 — Two cascaded active biquads (op‑amp based) with independent section tunings
  - Same general product form as above with (ωk, Qk) chosen per design.
- filter007 — RL low‑pass (series L, shunt R; Vout across R)
  - H(s) = R / (R + s L)
- filter008 — First‑order all‑pass (op‑amp implementation)
  - H(s) = (1 − s R C) / (1 + s R C)
- filter009 — Passive twin‑T notch (band‑stop)
  - H(s) = (s^2 + ω0^2) / (s^2 + (ω0/Q) s + ω0^2)
- filter010 — Second‑order high‑pass (two‑pole)
  - H(s) = K s^2 / (s^2 + (ω0/Q) s + ω0^2)
- filter011 — Active band‑pass (one‑op‑amp, multiple‑feedback form)
  - H(s) = H0 (s/ω0) / ((s/ω0)^2 + (s/ω0)/Q + 1)
- filter012 — State‑variable biquad (BP output)
  - H(s) = ( (ω0/Q) s ) / ( s^2 + (ω0/Q) s + ω0^2 )

Notes

- Op‑amp is referenced as a subcircuit `OPAMP` and is not defined in these templates.
- Values marked `?` are intentionally unspecified for symbolic reasoning tasks and may not simulate as‑is.

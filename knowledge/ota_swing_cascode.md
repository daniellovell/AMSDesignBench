Topic: Output swing — cascoded/telescopic single‑stage OTA

Key relations
- High side: vout_max ≈ VDD - (Σ Vov of PMOS devices stacked at vout), e.g., Vov_pcas + Vov_pmirror (top devices that must stay saturated).
- Low side: vout_min ≈ Vov_tail + Vov_input + Vov_ncas (bottom‑side NMOS stack headrooms to keep saturation).

Assumptions and notes
- Stacked devices at the output node require cumulative headroom; smallest admissible swing is set by the sum of Vov across the relevant stack.
- Maintain saturation for all cascoding devices (both NMOS and PMOS paths).
- Use Vov (aka V*, ΔV) for overdrive notation; specify which devices contribute.

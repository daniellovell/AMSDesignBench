Topic: Output swing — two‑stage OTA (output set by second stage)

Key relations
- High side: vout_max ≈ VDD - Vov_p of the PMOS load at vout (e.g., second‑stage PMOS).
- Low side: vout_min ≈ Vov_n of the second‑stage NMOS at vout.

Assumptions and notes
- First stage internal nodes should remain saturated, but vout swing is set primarily by the second‑stage output devices.
- Maintain saturation (headroom ≥ Vov) for devices tied to vout.
- Use Vov (aka V*, ΔV) for overdrive notation.

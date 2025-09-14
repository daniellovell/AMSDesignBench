Topic: Output swing — 5T single‑stage (current‑mirror) OTA

Key relations
- High side: vout_max ≈ VDD - Vov_p(load at vout). Vov ≡ V* ≡ ΔV (overdrive).
- Low side: vout_min ≈ Vov_tail + Vov_input ≈ 2·Vov_n (tail NMOS + input NMOS must remain in saturation).

Assumptions and notes
- Devices directly tied to vout: PMOS mirror/load sets the high‑side headroom; the NMOS stack (tail + input) sets the low‑side headroom.
- Maintain saturation (headroom ≥ Vov) for all contributing devices.
- Use consistent notation: Vov_p for PMOS, Vov_n for NMOS; synonyms V*, ΔV.

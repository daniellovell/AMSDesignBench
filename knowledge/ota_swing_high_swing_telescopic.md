Topic: Output swing — single‑ended high‑swing telescopic cascode OTA

Key relations
- High side: vop_max ≈ VDD - 2·V* (two PMOS headrooms in the output path).
- Low side: vop_min ≈ 3·V* (tail NMOS + input NMOS + NMOS cascode must remain in saturation).

Assumptions and notes
- Wide‑swing mirror decouples PMOS output devices (e.g., M6/M7) overdrive V* from their VGS. Their V* can be intentionally small (e.g., ~0.1 V) while maintaining saturation.
- Single‑ended output at vop. Maintain saturation headroom for all stacked devices.
- Use V* ≡ Vov ≡ ΔV notation consistently; specify which devices contribute to each limit when explaining.

Topic: Output swing — single‑stage high‑swing current‑mirror OTA

Key relations
- High side: vout_max ≈ VDD - Vov_p of the PMOS device directly tied to vout.
- Low side: vout_min ≈ Vov_n of the NMOS mirror device directly tied to vout.

Assumptions and notes
- “High‑swing” output stage routes current to both rails; the devices directly connected to vout set the immediate headroom limits.
- Internal nodes should remain saturated, but the first‑order output swing limits are dominated by the vout‑connected PMOS/NMOS devices.
- Vov ≡ V* ≡ ΔV (overdrive).

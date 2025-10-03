Anchor guidance for judge: filter topology identification and symbolic H(s)

Key expectations

- Topology section must explicitly name a plausible filter class consistent with the artifact (e.g., low-pass RC, high-pass CR, RL low-pass, RLC resonant band-pass, all-pass, twin‑T notch, Sallen‑Key or MFB biquad, state‑variable).
- Transfer function section must present H(s) = Vout(s)/Vin(s) symbolically:
  - First-order RC/CR/RL: canonical 1/(1+sτ) or sτ/(1+sτ) or R/(R+sL), with τ named as RC or L/R.
  - Notch/Band-stop: (s^2+ω0^2)/(s^2+(ω0/Q)s+ω0^2).
  - Band-pass: H0 (s/ω0)/((s/ω0)^2 + (s/ω0)/Q + 1).
  - Second-order low/high-pass: 1/(s^2/(ω0^2) + (s/(Qω0)) + 1) or K s^2/(s^2 + (ω0/Q)s + ω0^2).
  - Cascaded sections: product of two biquads with possibly different ωk and Qk.
- Grounded evidence must reference actual IDs (R1, C1, L1, XU1, nets like vin/vout) present in the artifact inventory.
- Avoid numerical sizing; symbolic relationships are sufficient.

Common pitfalls

- Mislabeling filter type (e.g., calling a notch a band-pass) should not receive full credit.
- Giving only qualitative text without an explicit H(s) is insufficient.
- Citing components that do not exist in the artifact should be penalized.


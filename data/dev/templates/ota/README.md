OTA Family (templates)

This folder contains SPICE templates for the `ota` family used as artifacts in the LLM bench. Netlists intentionally avoid descriptive comments and may use `?` for component values so models must infer topology and derive circuit characteristics from structure alone.

Summary

| OTA ID | Topology | GBW | $R_{out}$ | Swing (max/min) |
|--------|----------|-----|-----------|-----------------|
| ota001 | 5-Transistor (5T) OTA | $\frac{g_m}{C_L}$ | $\frac{r_o}{2}$ | $V_{DD} - V_{ov,p}$ / $2 \cdot V_{ov,n}$ |
| ota002 | Telescopic Cascode (Differential) | $\frac{g_m}{C_L}$ | $\frac{g_m r_o^2}{2}$ | $V_{DD} - (V_{ov,pcas} + V_{ov,pmir})$ / $V_{ov,tail} + V_{ov,in} + V_{ov,ncas}$ |
| ota003 | High-Swing Current Mirror OTA | $\frac{g_m}{C_L} \cdot k$ | $r_{o,p} \parallel r_{o,n}$ | $V_{DD} - V_{ov,p}$ / $V_{ov,n}$ |
| ota004 | Two-Stage (uncomp) | $\frac{g_{m1} \cdot g_{m6} \cdot (r_{o2} \parallel r_{o4})}{C_L}$ | $r_{o6} \parallel r_{o7}$ | $V_{DD} - V_{ov,p}$ / $V_{ov,n}$ |
| ota005 | Single-Ended Telescopic (High-Swing) | $\frac{g_m}{C_L}$ | $\frac{g_m r_o^2}{2}$ | $V_{DD} - (V_{ov,pcas} + V_{ov,pmir})$ / $V_{ov,tail} + V_{ov,in} + V_{ov,ncas}$ |
| ota006 | Single-Ended Telescopic | $\frac{g_m}{C_L}$ | $\frac{g_m r_o^2}{2}$ | $V_{DD} - 2 \cdot V_{ov}$ / $3 \cdot V_{ov}$ |

**Notation:**
- $g_m$ — transconductance of input differential pair
- $C_L$ — load capacitance
- $r_o$ — small-signal output resistance of a single transistor
- $V_{ov}$ — overdrive voltage (also denoted $V^*$ or $\Delta V$)
- $k$ — current mirror ratio (ota003 only)
- Subscripts: $p$ (PMOS), $n$ (NMOS), $pcas$ (PMOS cascode), $ncas$ (NMOS cascode), $pmir$ (PMOS mirror)

Topology Details

### ota001 — 5-Transistor OTA
- **Structure**: NMOS differential pair (M1, M2) with NMOS tail (Mtail)
- **Load**: PMOS current mirror (Mp2 diode-connected, Mp1 mirror output)
- **Output**: Single-ended at `vout`
- **Characteristics**: Simple, low power, moderate gain

### ota002 — Telescopic Cascode (Fully Differential)
- **Structure**: NMOS differential pair (M3, M4) with NMOS tail (M5)
- **Cascodes**: NMOS cascodes (M1, M2) and PMOS cascodes (M6, M7)
- **Load**: PMOS current mirrors (M8, M9)
- **Output**: Fully differential (vop, von)
- **Characteristics**: High gain, high speed, limited output swing

### ota003 — High-Swing Current Mirror OTA
- **Structure**: NMOS differential pair (M1, M2) with NMOS tail (Mtail)
- **Load**: Multiple PMOS current mirrors (M3 diode, M4, M5, M6) and NMOS mirror output stage (M7 diode, M8)
- **Output**: Single-ended at `vout` with push-pull capability (PMOS M6 and NMOS M8)
- **Characteristics**: Enhanced output swing, current mirror gain factor $k$, rail-to-rail operation

### ota004 — Two-Stage Miller OTA
- **First Stage**: NMOS differential pair (M1, M2) with PMOS current mirror (M3, M4)
- **Second Stage**: NMOS common-source amplifier (M6) with PMOS load (M7)
- **Compensation**: Load capacitor provides frequency compensation
- **Output**: Single-ended at `vout`
- **Characteristics**: High gain, rail-to-rail output, requires compensation

### ota005 — Single-Ended Telescopic (High-Swing)
- **Structure**: NMOS differential pair (M3, M4) with NMOS tail (M5)
- **Cascodes**: NMOS cascodes (M1, M2), PMOS with diode biasing (M6)
- **Biasing**: Diode-connected PMOS for high-swing biasing
- **Output**: Single-ended at `vop`
- **Characteristics**: Enhanced output swing, single-ended

### ota006 — Single-Ended Telescopic
- **Structure**: NMOS differential pair (M3, M4) with NMOS tail (M5)
- **Cascodes**: NMOS cascodes (M1, M2), PMOS cascodes (M6, M7)
- **Load**: PMOS diode and mirror (M8, M9)
- **Output**: Single-ended at `vop`
- **Characteristics**: Standard telescopic with single-ended output

Notes

- MOS body connections: NMOS bulk to `0` (GND), PMOS bulk to `VDD`
- Values marked `?` are intentionally unspecified for symbolic reasoning tasks and may not simulate as-is
- Bias voltages (vb1, vb2, vb3, vbp, vbn, vtail) are assumed externally provided
- Load capacitors (C1, C2, CL, Cload) represent external or parasitic loads


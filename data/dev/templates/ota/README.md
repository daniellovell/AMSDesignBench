OTA Family (templates)

This folder contains SPICE templates for the `ota` family used as artifacts in the LLM bench. Netlists intentionally avoid descriptive comments and may use `?` for component values so models must infer topology and derive circuit characteristics from structure alone.

Summary

| OTA ID | Topology | GBW | $R_{out}$ | Swing (max/min) |
|--------|----------|-----|-----------|-----------------|
| ota001 | 5-Transistor (5T) OTA | $\frac{g_m}{C_L}$ | $r_{o,p} \parallel r_{o,n}$ | $V_{DD} - V_{ov,p}$ / $2 \cdot V_{ov,n}$ |
| ota002 | Telescopic Cascode (Differential) | $\frac{g_m}{C_L}$ | $\frac{g_m r_o^2}{2}$ | $V_{DD} - (V_{ov,pcas} + V_{ov,pmir})$ / $V_{ov,tail} + V_{ov,in} + V_{ov,ncas}$ |
| ota003 | High-Swing Current Mirror OTA | $\frac{g_m}{C_L} \cdot k$ | $r_{o,p} \parallel r_{o,n}$ | $V_{DD} - V_{ov,p}$ / $V_{ov,n}$ |
| ota004 | Two-Stage (uncomp) | $\frac{g_{m1} \cdot g_{m6} \cdot (r_{o2} \parallel r_{o4})}{C_L}$ | $r_{o,p} \parallel r_{o,n}$ | $V_{DD} - V_{ov,p}$ / $V_{ov,n}$ |
| ota005 | Single-Ended Telescopic (High-Swing) | $\frac{g_m}{C_L}$ | $\frac{g_m r_o^2}{2}$ | $V_{DD} - (V_{ov,pcas} + V_{ov,pmir})$ / $V_{ov,tail} + V_{ov,in} + V_{ov,ncas}$ |
| ota006 | Single-Ended Telescopic | $\frac{g_m}{C_L}$ | $\frac{g_m r_o^2}{2}$ | $V_{DD} - 2 \cdot V_{ov}$ / $3 \cdot V_{ov}$ |
| ota007 | Common-Source (NMOS input, PMOS load) | $\frac{g_m}{C_L}$ | $r_{o,n} \parallel r_{o,p}$ | $V_{DD} - V_{ov,load}$ / $V_{ov,in}$ |
| ota008 | Folded Cascode (Single-Ended) | $\frac{g_m}{C_L}$ | $\frac{g_m r_o^2}{2}$ | $V_{DD} - (V_{ov,pcas} + V_{ov,load})$ / $V_{ov,in} + V_{ov,ncas}$ |
| ota009 | Regulated Cascode (Gain-Boosted) | $\frac{g_m}{C_L}$ | $(g_m r_o)^2 \cdot r_o$ | $V_{DD} - (V_{ov,pcas} + V_{ov,load})$ / $V_{ov,in} + V_{ov,ncas}$ |
| ota010 | Folded Cascode (Fully Differential, PMOS input) | $\frac{g_m}{C_L}$ | $g_m r_o^2$ | $V_{DD} - V_{ov,pcas}$ / $V_{ov,ncas}$ |
| ota011 | Folded Cascode (Fully Diff., High-Swing, PMOS input) | $\frac{g_m}{C_L}$ | $g_m r_o$ | $V_{DD} - V_{ov,pcas}$ / $V_{ov,ncas}$ |
| ota012 | Folded Cascode (Fully Diff., Diode-biased, PMOS input) | $\frac{g_m}{C_L}$ | $g_m r_o^2$ | $V_{DD} - V_{ov,pcas}$ / $V_{ov,ncas}$ |

**Notation:**
- $g_m$ — transconductance of input differential pair
- $C_L$ — load capacitance
- $r_o$ — small-signal output resistance of a single transistor
- $V_{ov}$ — overdrive voltage (also denoted $V^*$ or $\Delta V$)
- $k$ — current mirror ratio (ota003 only)
- Subscripts: $p$ (PMOS), $n$ (NMOS), $pcas$ (PMOS cascode), $ncas$ (NMOS cascode), $pmir$ (PMOS mirror)

Analysis Questions

Each OTA topology is evaluated with the following analysis questions (track: `analysis`):

| Question Aspect | Description | Example Answer Key (ota001) |
|----------------|-------------|------------------------------|
| **GBW** | Derive the gain-bandwidth product | GBW ≈ gm/CL for single-pole one-stage OTA |
| **Rout** | Determine output resistance | (ro_nmos \|\| ro_pmos) at vout |
| **Swing** | Calculate output voltage swing limits | High: VDD - Vov_p; Low: 2·Vov_n |
| **DC Gain** | Derive the DC small-signal gain | Symbolic expression in terms of gm and ro |
| **PSRR** | Analyze power supply rejection ratio | Symbolic PSRR+ and/or PSRR- expressions |
| **Noise (White)** | Calculate input-referred white noise | Noise contributions from input pair and loads |
| **Power (Quiescent)** | Calculate quiescent power consumption | P = VDD × (sum of all bias currents) |

**Note**: Answer keys vary by topology. For example:
- **ota002** (Telescopic): Rout ≈ (gm·ro²)/2 (cascode effect)
- **ota004** (Two-Stage): GBW ∝ gm1·gm6·(ro2\|\|ro4)/CL when β≈1

Debugging Questions

Each OTA topology includes a debugging task (track: `debugging`):

| Question Aspect | Description | Answer Key |
|----------------|-------------|------------|
| **Device Swap** | Identify swapped PMOS/NMOS device and propose fix | Identify specific device (e.g., M1), explain type mismatch (PMOS vs NMOS), propose concrete fix including body connection |

**Example debugging fault**: A PMOS transistor is incorrectly instantiated as NMOS (or vice versa), breaking circuit functionality. Models must identify the faulty device and specify the correct device type and body connection.

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

### ota007 — Common-Source Amplifier
- **Structure**: Single NMOS input transistor (M2) in common-source configuration
- **Load**: PMOS current source (M1) connected to VDD
- **Output**: Single-ended at `vout`
- **Characteristics**: Simplest single-transistor amplifier, inverting gain, moderate output resistance

### ota008 — Folded Cascode (Single-Ended)
- **Structure**: Single NMOS input (M1) with NMOS cascode (M2)
- **Cascodes**: PMOS cascode (M3) above output with PMOS current source (M4)
- **Output**: Single-ended at `vout`
- **Characteristics**: High output resistance from cascode, improved swing compared to telescopic

### ota009 — Regulated Cascode (Gain-Boosted)
- **Structure**: NMOS input (M1) with NMOS cascode (M2), PMOS cascode (M3) and PMOS source (M4)
- **Gain Boosting**: Two auxiliary gain-boosting amplifiers regulate cascode gates:
  - PMOS gain-boosting stage (M6, M7) for PMOS cascode
  - NMOS gain-boosting stage (M5, M8) for NMOS cascode
- **Output**: Single-ended at `vout`
- **Characteristics**: Very high output resistance $(g_m r_o)^2 \cdot r_o$ due to regulation, enhanced gain

### ota010 — Folded Cascode (Fully Differential, PMOS input)
- **Structure**: PMOS differential pair (M1, M2) with PMOS tail (M3)
- **Cascodes**: PMOS cascodes (M6, M7) on top, NMOS cascodes (M8, M10) below
- **Current Sources**: PMOS top sources (M4, M5), NMOS bottom sources (M9, M11)
- **Output**: Fully differential (voutp, voutn)
- **Characteristics**: Folded topology with PMOS input for better PMOS matching, high output resistance

### ota011 — Folded Cascode with High-Swing Biasing (PMOS input)
- **Structure**: PMOS differential pair (M1, M2) with PMOS tail (M3) and tail cascode (M12)
- **High-Swing PMOS Stage**: Diode-connected pre-devices (M4, M5) with cascodes (M6, M7) for improved swing
- **NMOS Cascodes**: Standard NMOS cascodes (M8, M10) with sources (M9, M11)
- **Output**: Single-ended at `vout`
- **Characteristics**: Enhanced output swing with high-swing cascode biasing technique

### ota012 — Folded Cascode with Diode Biasing (PMOS input)
- **Structure**: PMOS differential pair (M1, M2) with cascoded tail (M3, M12)
- **Diode-Connected Biasing**: Two-stage diode chain (M4, M5) with cascodes (M6, M7) generates stable bias
- **NMOS Cascodes**: Standard NMOS cascodes (M8, M10) with sources (M9, M11)
- **Output**: Single-ended at `vout`
- **Characteristics**: Diode-based bias generation for improved process/temperature stability

Notes

- MOS body connections: NMOS bulk to `0` (GND), PMOS bulk to `VDD`
- Values marked `?` are intentionally unspecified for symbolic reasoning tasks and may not simulate as-is
- Bias voltages (vb1, vb2, vb3, vb4, vb5, vbp, vbn, vtail) are assumed externally provided
- Load capacitors (C1, C2, CL, Cload) represent external or parasitic loads
- Gain-boosted and regulated cascodes (ota009) achieve output resistance proportional to $(g_m r_o)^2 r_o$ or $g_m r_o^3$


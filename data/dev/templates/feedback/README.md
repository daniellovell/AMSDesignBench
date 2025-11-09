Feedback Amplifiers Family (templates)

This folder contains SPICE templates for the `feedback` family used as artifacts in the LLM bench. Netlists intentionally avoid descriptive comments and may use `?` for component values so models must infer topology and derive circuit characteristics from structure alone.

Summary

| Feedback ID | Topology | Closed-Loop Gain | Signal Modality | Beta Factor | Loop Gain |
|-------------|----------|------------------|-----------------|-------------|-----------|
| feedback001 | Single-Ended TIA with Feedback Resistor | $-R_f$ | I→V | $\beta = 1$ | $T = A_{ol}$ |
| feedback002 | Single-Ended TIA with Feedback Capacitor | $-\frac{1}{sC_f}$ | I→V | $\beta = 1$ | $T = A_{ol}$ |
| feedback003 | Noninverting Voltage Amplifier | $1 + \frac{R_2}{R_1}$ | V→V | $\beta = \frac{R_1}{R_1+R_2}$ | $T = A_{ol}$ |
| feedback004 | Inverting Voltage Amplifier | $-\frac{R_2}{R_1}$ | V→V | $\beta = \frac{R_2}{R_1+R_2}$ | $T = A_{ol}$ |

**Notation:**
- $R_f$ — feedback resistor (transimpedance)
- $C_f$ — feedback capacitor
- $R_1, R_2$ — resistive feedback network elements
- I→V — current input, voltage output (transimpedance)
- V→V — voltage input, voltage output
- $\beta$ — feedback factor (fraction of output fed back)
- $A_{ol}$ — open-loop gain of op-amp
- $T$ — loop gain

Analysis Questions

Each feedback amplifier topology is evaluated with the following analysis questions (track: `analysis`):

| Question Aspect | Description | Example Answer Key (feedback001) |
|----------------|-------------|-----------------------------------|
| **Closed-Loop Gain** | Derive the closed-loop gain expression | $V_{out}/I_{in} = -R_1$ (transimpedance) |
| **Beta Factor** | Determine feedback factor $\beta$ | $\beta = 1$ (unity feedback) |
| **Loop Gain** | Calculate loop gain $T$ | $T = A_{ol}$ (open-loop gain) |
| **Signal Modality** | Identify input/output signal types | Current input to voltage output (I→V) |

**Answer keys by topology**:
- **feedback001** (TIA, R): Gain = -R₁, β = 1, Modality = I→V
- **feedback002** (TIA, C): Gain = -1/(sC₁), β = 1, Modality = I→V  
- **feedback003** (Non-inverting): Gain = 1 + R₂/R₁, β = R₁/(R₁+R₂), Modality = V→V
- **feedback004** (Inverting): Gain = -R₂/R₁, β = R₂/(R₁+R₂), Modality = V→V

Debugging Questions

Each feedback amplifier topology includes a debugging task (track: `debugging`):

| Question Aspect | Description | Answer Key |
|----------------|-------------|------------|
| **Feedback Polarity** | Identify incorrect feedback polarity and propose fix | Detect positive vs. negative feedback configuration, identify problematic connections (op-amp inputs, resistor nodes), propose concrete fix (swap inputs or correct node connections) |

**Example debugging fault**: Op-amp inputs are swapped or feedback resistor is connected incorrectly, creating positive feedback instead of negative feedback. This causes instability, oscillation, or saturation. Models must identify the fault and specify the correct configuration for stable negative feedback operation.

Topology Details

### feedback001 — Single-Ended TIA with Feedback Resistor
- **Structure**: Opamp with inverting input as signal input, non-inverting input grounded, resistor from output to inverting input
- **Feedback**: Resistive negative feedback
- **Signal Modality**: Current-to-voltage (I-V)
- **Characteristics**: Constant transimpedance gain, current input buffer

### feedback002 — Single-Ended TIA with Feedback Capacitor
- **Structure**: Opamp with inverting input as signal input, non-inverting input grounded, capacitor from output to inverting input
- **Feedback**: Capacitive negative feedback
- **Signal Modality**: Current-to-voltage (I-V)
- **Characteristics**: Integrator behavior, frequency-dependent transimpedance

### feedback003 — Noninverting Voltage Amplifier
- **Structure**: Opamp with signal at non-inverting input, resistive divider from output to inverting input and ground
- **Feedback**: Resistive negative feedback via voltage divider
- **Signal Modality**: Voltage-to-voltage (V-V)
- **Characteristics**: Positive closed-loop gain (≥1), high input impedance

### feedback004 — Inverting Voltage Amplifier
- **Structure**: Opamp with non-inverting input grounded, signal through input resistor to inverting input, feedback resistor from output to inverting input
- **Feedback**: Resistive negative feedback
- **Signal Modality**: Voltage-to-voltage (V-V)
- **Characteristics**: Negative closed-loop gain, virtual ground at inverting input

Notes

- Op-amp is referenced as a subcircuit `opamp` with parameters `Aol` (open-loop gain) and `GBW` (gain-bandwidth product)
- Values marked `?` or symbolic (`R`, `C`) are intentionally unspecified for symbolic reasoning tasks and may not simulate as-is
- All circuits implement negative feedback for stable operation
- Loop gain typically equals $A_{ol}$ for TIA configurations, and $A_{ol} \cdot \beta$ for voltage amplifiers where $\beta$ is the feedback factor


Feedback Amplifiers Family (templates)

This folder contains SPICE templates for the `feedback` family used as artifacts in the LLM bench. Netlists intentionally avoid descriptive comments and may use `?` for component values so models must infer topology and derive circuit characteristics from structure alone.

Summary

| Feedback ID | Topology | Closed-Loop Gain | Signal Modality |
|-------------|----------|------------------|-----------------|
| feedback001 | Single-Ended TIA with Feedback Resistor | $-R_f$ | I-V |
| feedback002 | Single-Ended TIA with Feedback Capacitor | $-\frac{1}{sC_f}$ | I-V |
| feedback003 | Noninverting Voltage Amplifier | $1 + \frac{R_2}{R_1}$ | V-V |
| feedback004 | Inverting Voltage Amplifier | $-\frac{R_1}{R_2}$ | V-V |

**Notation:**
- $R_f$ — feedback resistor (transimpedance)
- $C_f$ — feedback capacitor
- $R_1, R_2$ — resistive feedback network elements
- I-V — current input, voltage output (transimpedance)
- V-V — voltage input, voltage output

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


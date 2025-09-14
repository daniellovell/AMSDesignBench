Debugging: Device Polarity Swap (Generic)

Problem: A MOS device is instantiated with the wrong polarity (NMOS vs PMOS), which disrupts the intended biasing and reduces DC gain.

Symptoms:
- Incorrect DC operating point (e.g., output railed, tail current path broken, or mirror path inactive).
- Low or undefined gain.

What to check:
- Input differential pair devices should be NMOS for typical 5T-style OTAs with NMOS tail, or match the intended topology.
- PMOS loads/cascodes should be PMOS connected to VDD; NMOS devices should reference ground.
- Bodies: NMOS → 0 (GND), PMOS → VDD.

Fix approach:
- Change the device to the correct model type (e.g., `nch` ↔ `pch`) and correct the body tie as needed.
- Verify gate/source/drain orientation and node names remain consistent with the intended function.


Designing a Five-Transistor (5T) Current-Mirror OTA

Essentials:
- NMOS differential pair (two NMOS devices) with sources tied to a tail NMOS current source to ground.
- PMOS load as a current mirror to VDD: one PMOS diode-connected (gate-drain short) and the other PMOS providing the mirrored current at the output branch.
- Single-ended output (e.g., right branch) at node `vout`; load capacitor `CL` may be attached to ground.
- Supplies/nodes: `VDD` as positive rail, `0`/GND as reference. Bodies: NMOS to 0, PMOS to VDD.

Synthesis guidance:
- Provide a minimal SPICE-like netlist with placeholder dimensions (W=?, L=?). Naming is flexible.
- Ensure connectivity reflects the topology: gates of load PMOS mirror devices tied appropriately; differential pair gates to inputs; tail source biased.


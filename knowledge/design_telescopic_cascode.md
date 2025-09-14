Designing a Telescopic (Cascoded) Differential OTA

Essentials:
- NMOS differential pair with sources tied to an NMOS tail current source.
- NMOS cascodes above the inputs; PMOS cascodes as active loads up to VDD.
- Fully differential outputs (vop/von) at the top nodes; supply rails VDD and 0.
- Bodies: NMOS to 0, PMOS to VDD.

Synthesis guidance:
- Provide a minimal SPICE-like netlist with placeholder dimensions (W=?, L=?).
- Show cascode bias nodes for NMOS and PMOS stacks; ensure connectivity reflects telescopic structure.


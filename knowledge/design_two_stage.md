Designing a Two-Stage OTA

Essentials:
- First stage: differential pair and load produce an intermediate node.
- Second stage: gain device(s) with load at the output; single-ended output with load to ground.
- Supplies/nodes: VDD, GND; bodies tied appropriately (NMOS→0, PMOS→VDD).

Synthesis guidance:
- Provide a minimal SPICE-like netlist with placeholder W/L; show distinct first and second stages via node naming or comments.


Designing a Single-Stage High-Swing Current-Mirror OTA

Essentials:
- NMOS differential pair and an NMOS tail current source.
- PMOS load devices connected to VDD; additional mirror branch uses NMOS to reference ground, enabling a larger swing at the single-ended output.
- Output at the branch with mirrored current; load capacitor can connect to ground.

Synthesis guidance:
- Provide a minimal SPICE-like netlist with placeholder dimensions (W=?, L=?), emphasizing connectivity (mirror devices, diode connections).


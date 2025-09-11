* ota004: classic two-stage op-amp WITHOUT Miller compensation
* NMOS-input first stage with PMOS active load -> NMOS common-source second stage with PMOS active load
*
* Key small-signal relations (pre-compensation):
*   GBW ≈ gm1 * gm6 * (ro2 || ro4) / CL
*   Rout(vout) ≈ ro6 || ro7
*
* Node naming:
*   vinp, vinn  : differential inputs
*   vint        : first-stage single-ended output (internal node)
*   vout        : amplifier output
*   vdd, 0      : supplies
*   vbn, vbp    : bias nodes (NMOS tail, PMOS load)

.title ota004_two_stage_no_miller

* Power supplies and simple biases (values are placeholders)
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

* Load capacitor at output (CL)
C_L vout 0 1p

* First stage: NMOS differential pair with PMOS active load (current-mirror)
* M1 contributes gm1; first-stage output resistance is (ro2 || ro4) at node 'vint'
M1 n1   vinp ntail 0 NMOS W=10u L=0.18u
M2 vint vinn ntail 0 NMOS W=10u L=0.18u   
M3 n1   n1   vdd   vdd PMOS W=20u L=0.18u   * diode-connected PMOS (mirror ref)
M4 vint n1   vdd   vdd PMOS W=20u L=0.18u   * PMOS active load at first-stage output
M5 ntail vbn  0     0 NMOS W=5u  L=0.18u    * NMOS tail current source

* Second stage: NMOS common-source with PMOS active load
* M6 provides gm6; output resistance at vout is (ro6 || ro7)
M6 vout vint 0     0 NMOS W=40u L=0.18u
M7 vout vbp vdd   vdd PMOS W=40u L=0.18u

* Simple level-1 MOS models (placeholders suitable for schematic-level reasoning)
.model NMOS nmos level=1 kp=200e-6 vt0=0.5 lambda=0.02
.model PMOS pmos level=1 kp=100e-6 vt0=-0.5 lambda=0.02

.end


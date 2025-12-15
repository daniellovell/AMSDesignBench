
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C984745000 vout 0 1p

M991255162 n1 vinp ntail 0 NMOS W=10u L=0.18u
M168248226 vint vinn ntail 0 NMOS W=10u L=0.18u
M253903081 n1 n1 vdd vdd PMOS W=20u L=0.18u
M348798627 vint n1 vdd vdd PMOS W=20u L=0.18u
M355766197 ntail vbn 0 0 NMOS W=5u L=0.18u

M738106589 vout vint 0 0 NMOS W=40u L=0.18u
M273023499 vout vbp vdd vdd PMOS W=40u L=0.18u


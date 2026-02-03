
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C656065134 vout 0 1p

M713829675 n1 vinp ntail 0 NMOS W=10u L=0.18u
M753877598 vint vinn ntail 0 NMOS W=10u L=0.18u
M213886406 n1 n1 vdd vdd PMOS W=20u L=0.18u
M355537453 vint n1 vdd vdd PMOS W=20u L=0.18u
M202234081 ntail vbn 0 0 NMOS W=5u L=0.18u

M495479760 vout vint 0 0 NMOS W=40u L=0.18u
M44518434 vout vbp vdd vdd PMOS W=40u L=0.18u


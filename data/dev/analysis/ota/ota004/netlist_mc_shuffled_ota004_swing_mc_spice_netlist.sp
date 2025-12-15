
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C276536805 vout 0 1p

M383038060 n1 vinp ntail 0 NMOS W=10u L=0.18u
M301408649 vint vinn ntail 0 NMOS W=10u L=0.18u
M605428531 n1 n1 vdd vdd PMOS W=20u L=0.18u
M286376121 vint n1 vdd vdd PMOS W=20u L=0.18u
M528367303 ntail vbn 0 0 NMOS W=5u L=0.18u

M511168353 vout vint 0 0 NMOS W=40u L=0.18u
M109186041 vout vbp vdd vdd PMOS W=40u L=0.18u


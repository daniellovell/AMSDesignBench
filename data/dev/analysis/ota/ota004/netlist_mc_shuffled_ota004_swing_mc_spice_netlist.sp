
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C303435054 vout 0 1p

M712863570 n1 vinp ntail 0 NMOS W=10u L=0.18u
M846826555 vint vinn ntail 0 NMOS W=10u L=0.18u
M871296387 n1 n1 vdd vdd PMOS W=20u L=0.18u
M513467014 vint n1 vdd vdd PMOS W=20u L=0.18u
M971942335 ntail vbn 0 0 NMOS W=5u L=0.18u

M326771231 vout vint 0 0 NMOS W=40u L=0.18u
M851057877 vout vbp vdd vdd PMOS W=40u L=0.18u


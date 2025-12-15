
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C828755462 vout 0 1p

M851939267 n1 vinp ntail 0 NMOS W=10u L=0.18u
M753412595 vint vinn ntail 0 NMOS W=10u L=0.18u
M323200515 n1 n1 vdd vdd PMOS W=20u L=0.18u
M245843200 vint n1 vdd vdd PMOS W=20u L=0.18u
M805543599 ntail vbn 0 0 NMOS W=5u L=0.18u

M815994818 vout vint 0 0 NMOS W=40u L=0.18u
M838470523 vout vbp vdd vdd PMOS W=40u L=0.18u


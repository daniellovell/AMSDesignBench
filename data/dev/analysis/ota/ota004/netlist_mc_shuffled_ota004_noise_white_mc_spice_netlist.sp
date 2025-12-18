
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C555685463 vout 0 1p

M20511808 n1 vinp ntail 0 NMOS W=10u L=0.18u
M753531969 vint vinn ntail 0 NMOS W=10u L=0.18u
M837145062 n1 n1 vdd vdd PMOS W=20u L=0.18u
M563301537 vint n1 vdd vdd PMOS W=20u L=0.18u
M511451796 ntail vbn 0 0 NMOS W=5u L=0.18u

M145733397 vout vint 0 0 NMOS W=40u L=0.18u
M712994309 vout vbp vdd vdd PMOS W=40u L=0.18u


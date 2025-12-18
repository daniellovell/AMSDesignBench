
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C765496346 vout 0 1p

M980929564 n1 vinp ntail 0 NMOS W=10u L=0.18u
M221171987 vint vinn ntail 0 NMOS W=10u L=0.18u
M885028558 n1 n1 vdd vdd PMOS W=20u L=0.18u
M448498500 vint n1 vdd vdd PMOS W=20u L=0.18u
M3680426 ntail vbn 0 0 NMOS W=5u L=0.18u

M82300833 vout vint 0 0 NMOS W=40u L=0.18u
M325904888 vout vbp vdd vdd PMOS W=40u L=0.18u


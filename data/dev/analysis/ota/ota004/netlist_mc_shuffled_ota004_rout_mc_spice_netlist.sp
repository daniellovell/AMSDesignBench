
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C909246610 vout 0 1p

M388644097 n1 vinp ntail 0 NMOS W=10u L=0.18u
M22305349 vint vinn ntail 0 NMOS W=10u L=0.18u
M484574367 n1 n1 vdd vdd PMOS W=20u L=0.18u
M563290552 vint n1 vdd vdd PMOS W=20u L=0.18u
M739022277 ntail vbn 0 0 NMOS W=5u L=0.18u

M190840502 vout vint 0 0 NMOS W=40u L=0.18u
M943164498 vout vbp vdd vdd PMOS W=40u L=0.18u


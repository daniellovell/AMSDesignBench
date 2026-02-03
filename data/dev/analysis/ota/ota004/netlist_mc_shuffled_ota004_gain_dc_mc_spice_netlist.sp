
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C705472429 vout 0 1p

M875189157 n1 vinp ntail 0 NMOS W=10u L=0.18u
M220176988 vint vinn ntail 0 NMOS W=10u L=0.18u
M886048040 n1 n1 vdd vdd PMOS W=20u L=0.18u
M49542292 vint n1 vdd vdd PMOS W=20u L=0.18u
M915034427 ntail vbn 0 0 NMOS W=5u L=0.18u

M74040807 vout vint 0 0 NMOS W=40u L=0.18u
M187962979 vout vbp vdd vdd PMOS W=40u L=0.18u


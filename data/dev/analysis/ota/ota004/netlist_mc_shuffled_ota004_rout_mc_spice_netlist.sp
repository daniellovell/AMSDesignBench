
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C257885317 vout 0 1p

M310226204 n1 vinp ntail 0 NMOS W=10u L=0.18u
M266403673 vint vinn ntail 0 NMOS W=10u L=0.18u
M459779726 n1 n1 vdd vdd PMOS W=20u L=0.18u
M800638078 vint n1 vdd vdd PMOS W=20u L=0.18u
M35875594 ntail vbn 0 0 NMOS W=5u L=0.18u

M868156492 vout vint 0 0 NMOS W=40u L=0.18u
M784387148 vout vbp vdd vdd PMOS W=40u L=0.18u


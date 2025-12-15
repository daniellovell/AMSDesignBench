
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C381405184 vout 0 1p

M689405299 n1 vinp ntail 0 NMOS W=10u L=0.18u
M512552227 vint vinn ntail 0 NMOS W=10u L=0.18u
M461788584 n1 n1 vdd vdd PMOS W=20u L=0.18u
M211400483 vint n1 vdd vdd PMOS W=20u L=0.18u
M861581171 ntail vbn 0 0 NMOS W=5u L=0.18u

M48770038 vout vint 0 0 NMOS W=40u L=0.18u
M948096102 vout vbp vdd vdd PMOS W=40u L=0.18u


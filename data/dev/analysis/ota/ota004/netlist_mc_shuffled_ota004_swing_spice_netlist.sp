
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C858965748 vout 0 1p

M53412977 n1 vinp ntail 0 NMOS W=10u L=0.18u
M884262 vint vinn ntail 0 NMOS W=10u L=0.18u
M772800600 n1 n1 vdd vdd PMOS W=20u L=0.18u
M14504057 vint n1 vdd vdd PMOS W=20u L=0.18u
M135462875 ntail vbn 0 0 NMOS W=5u L=0.18u

M24104188 vout vint 0 0 NMOS W=40u L=0.18u
M265289530 vout vbp vdd vdd PMOS W=40u L=0.18u


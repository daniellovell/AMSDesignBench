
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C142783374 vout 0 1p

M306312908 n1 vinp ntail 0 NMOS W=10u L=0.18u
M220302124 vint vinn ntail 0 NMOS W=10u L=0.18u
M393034181 n1 n1 vdd vdd PMOS W=20u L=0.18u
M72276251 vint n1 vdd vdd PMOS W=20u L=0.18u
M425972735 ntail vbn 0 0 NMOS W=5u L=0.18u

M239312598 vout vint 0 0 NMOS W=40u L=0.18u
M298833979 vout vbp vdd vdd PMOS W=40u L=0.18u


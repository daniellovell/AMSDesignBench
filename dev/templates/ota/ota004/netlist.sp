
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

Cload vout 0 1p

M1 n1   vinp ntail 0 NMOS W=10u L=0.18u
M2 vint vinn ntail 0 NMOS W=10u L=0.18u   
M3 n1   n1   vdd   vdd PMOS W=20u L=0.18u   
M4 vint n1   vdd   vdd PMOS W=20u L=0.18u   
M5 ntail vbn  0     0 NMOS W=5u  L=0.18u    

M6 vout vint 0     0 NMOS W=40u L=0.18u
M7 vout vbp vdd   vdd PMOS W=40u L=0.18u


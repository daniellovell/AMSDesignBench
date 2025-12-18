
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C392127897 vout 0 1p

M758518460 n1 vinp ntail 0 NMOS W=10u L=0.18u
M193536121 vint vinn ntail 0 NMOS W=10u L=0.18u
M11192874 n1 n1 vdd vdd PMOS W=20u L=0.18u
M225532886 vint n1 vdd vdd PMOS W=20u L=0.18u
M162898963 ntail vbn 0 0 NMOS W=5u L=0.18u

M762089240 vout vint 0 0 NMOS W=40u L=0.18u
M980596571 vout vbp vdd vdd PMOS W=40u L=0.18u


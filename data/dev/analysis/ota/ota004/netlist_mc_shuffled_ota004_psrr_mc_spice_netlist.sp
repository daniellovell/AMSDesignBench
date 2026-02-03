
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C300821082 vout 0 1p

M337065967 n1 vinp ntail 0 NMOS W=10u L=0.18u
M923382898 vint vinn ntail 0 NMOS W=10u L=0.18u
M546594902 n1 n1 vdd vdd PMOS W=20u L=0.18u
M105025498 vint n1 vdd vdd PMOS W=20u L=0.18u
M744254120 ntail vbn 0 0 NMOS W=5u L=0.18u

M490613432 vout vint 0 0 NMOS W=40u L=0.18u
M238630034 vout vbp vdd vdd PMOS W=40u L=0.18u


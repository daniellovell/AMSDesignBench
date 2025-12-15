
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C441674842 vout 0 1p

M782718245 n1 vinp ntail 0 NMOS W=10u L=0.18u
M148798893 vint vinn ntail 0 NMOS W=10u L=0.18u
M590467847 n1 n1 vdd vdd PMOS W=20u L=0.18u
M611797244 vint n1 vdd vdd PMOS W=20u L=0.18u
M607182199 ntail vbn 0 0 NMOS W=5u L=0.18u

M29053329 vout vint 0 0 NMOS W=40u L=0.18u
M322336859 vout vbp vdd vdd PMOS W=40u L=0.18u


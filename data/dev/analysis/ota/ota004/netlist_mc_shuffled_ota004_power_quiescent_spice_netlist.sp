
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C906737741 vout 0 1p

M108666389 n1 vinp ntail 0 NMOS W=10u L=0.18u
M996710114 vint vinn ntail 0 NMOS W=10u L=0.18u
M646251685 n1 n1 vdd vdd PMOS W=20u L=0.18u
M313765228 vint n1 vdd vdd PMOS W=20u L=0.18u
M136531005 ntail vbn 0 0 NMOS W=5u L=0.18u

M160375752 vout vint 0 0 NMOS W=40u L=0.18u
M87624288 vout vbp vdd vdd PMOS W=40u L=0.18u


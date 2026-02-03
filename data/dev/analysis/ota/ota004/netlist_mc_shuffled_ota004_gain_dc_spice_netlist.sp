
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C758573628 vout 0 1p

M510872310 n1 vinp ntail 0 NMOS W=10u L=0.18u
M950226577 vint vinn ntail 0 NMOS W=10u L=0.18u
M880945012 n1 n1 vdd vdd PMOS W=20u L=0.18u
M817915732 vint n1 vdd vdd PMOS W=20u L=0.18u
M454417931 ntail vbn 0 0 NMOS W=5u L=0.18u

M647361644 vout vint 0 0 NMOS W=40u L=0.18u
M671087455 vout vbp vdd vdd PMOS W=40u L=0.18u


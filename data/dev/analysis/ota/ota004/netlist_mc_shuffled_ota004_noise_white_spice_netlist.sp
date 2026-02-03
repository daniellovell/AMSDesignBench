
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C419444956 vout 0 1p

M726077378 n1 vinp ntail 0 NMOS W=10u L=0.18u
M453627536 vint vinn ntail 0 NMOS W=10u L=0.18u
M513517341 n1 n1 vdd vdd PMOS W=20u L=0.18u
M396114898 vint n1 vdd vdd PMOS W=20u L=0.18u
M417541565 ntail vbn 0 0 NMOS W=5u L=0.18u

M62141533 vout vint 0 0 NMOS W=40u L=0.18u
M741726312 vout vbp vdd vdd PMOS W=40u L=0.18u


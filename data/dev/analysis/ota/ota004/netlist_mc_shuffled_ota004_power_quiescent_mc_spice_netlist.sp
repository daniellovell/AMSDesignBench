
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C804830675 vout 0 1p

M168758096 n1 vinp ntail 0 NMOS W=10u L=0.18u
M931657229 vint vinn ntail 0 NMOS W=10u L=0.18u
M596086918 n1 n1 vdd vdd PMOS W=20u L=0.18u
M410103267 vint n1 vdd vdd PMOS W=20u L=0.18u
M341016412 ntail vbn 0 0 NMOS W=5u L=0.18u

M782678794 vout vint 0 0 NMOS W=40u L=0.18u
M340808843 vout vbp vdd vdd PMOS W=40u L=0.18u


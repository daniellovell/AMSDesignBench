
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C126775708 vout 0 1p

M981751211 n1 vinp ntail 0 NMOS W=10u L=0.18u
M557574776 vint vinn ntail 0 NMOS W=10u L=0.18u
M267671823 n1 n1 vdd vdd PMOS W=20u L=0.18u
M385273815 vint n1 vdd vdd PMOS W=20u L=0.18u
M597327059 ntail vbn 0 0 NMOS W=5u L=0.18u

M409317242 vout vint 0 0 NMOS W=40u L=0.18u
M635899712 vout vbp vdd vdd PMOS W=40u L=0.18u


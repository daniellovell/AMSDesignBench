
VDD vdd 0 1.8
VBP vbp 0 0.9
VBN vbn 0 0.7
VINP vinp 0 0
VINN vinn 0 0

C7819591 vout 0 1p

M13989082 n1 vinp ntail 0 NMOS W=10u L=0.18u
M818641801 vint vinn ntail 0 NMOS W=10u L=0.18u
M237511722 n1 n1 vdd vdd PMOS W=20u L=0.18u
M394416947 vint n1 vdd vdd PMOS W=20u L=0.18u
M173460163 ntail vbn 0 0 NMOS W=5u L=0.18u

M614913160 vout vint 0 0 NMOS W=40u L=0.18u
M976285246 vout vbp vdd vdd PMOS W=40u L=0.18u


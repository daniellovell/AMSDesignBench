* telescopic cascode single-stage OTA (structural)
* Nodes: vinp, vinn, vout, VDD, vbias_n (tail), vb_ncasc (NMOS cascode), vb_pcasc (PMOS cascode)
M1 n1 vinp ntail 0 nch W=2u L=0.18u
M2 n2 vinn ntail 0 nch W=2u L=0.18u
* NMOS cascodes above input pair
M3 n3 vb_ncasc n1 0 nch W=1u L=0.18u
M4 n4 vb_ncasc n2 0 nch W=1u L=0.18u
* Tail current source
M9 ntail vbias_n 0 0 nch W=1u L=0.5u
* PMOS mirror with PMOS cascodes on top
M5 n5 vb_pcasc n3 VDD pch W=2u L=0.18u
M6 vout vb_pcasc n4 VDD pch W=2u L=0.18u
M7 n5 n5 VDD VDD pch W=4u L=0.18u
M8 vout n5 VDD VDD pch W=4u L=0.18u
VDD VDD 0 1.8
Cload vout 0 1p
* Single pole dominated by CL, GBW ≈ gm/CL


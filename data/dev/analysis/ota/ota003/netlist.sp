M1 n1 vinp ntail 0 nch W=2u L=0.18u
M2 n2 vinn ntail 0 nch W=2u L=0.18u
Mtail ntail vbias_n 0 0 nch W=1u L=0.5u

* Inner 5T OTA active load (PMOS current mirror)
M3 n1 n1 VDD VDD pch W=2u L=0.18u       ; left PMOS (diode-connected)
M4 n2 n1 VDD VDD pch W=2u L=0.18u       ; right PMOS (mirrored to right branch)

* Mirror the two PMOS currents outward
M5 nmir n1 VDD VDD pch W=4u L=0.18u     ; mirrored left current (to NMOS mirror)
M6 vout n1 VDD VDD pch W=4u L=0.18u     ; mirrored right current directly to output

* NMOS current mirror fed by M5; output tied to vout
M7 nmir nmir 0 0 nch W=2u L=0.18u       ; diode-connected reference
M8 vout nmir 0 0 nch W=2u L=0.18u       ; mirrored sink at output

VDD VDD 0 1.8
Cload vout 0 1p


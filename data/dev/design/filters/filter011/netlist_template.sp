Vin vin 0 AC 1
* Series RLC band-pass core (tune f0 and Q)
L1 vin n1 BLANK
C1 n1 vraw BLANK
Rbp vraw 0 BLANK
* Gain stage (non-inverting): gain = 1 + Rfb/Rg (target |gain| = 2 -> Rfb = Rg)
Rg nneg 0 BLANK
Rfb vout nneg BLANK
XU1 vout nneg vraw OPAMP
Rload vout 0 BLANK

.end

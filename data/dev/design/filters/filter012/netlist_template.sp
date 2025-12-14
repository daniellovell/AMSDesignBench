Vin vin 0 AC 1

* Series RLC band-pass core (tune f0 and Q)
L1 vin n1 BLANK
C1 n1 vraw BLANK
Rbp vraw 0 BLANK
* Buffer (voltage follower)
XU1 vout vout vraw OPAMP
Rload vout 0 BLANK

.end

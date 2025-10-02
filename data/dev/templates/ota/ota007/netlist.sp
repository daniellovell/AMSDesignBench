* /Users/kesvis/Documents/LTspice/nmos_common_source_active_load.asc
M2 vout vin 0 0 NMOS l=0.18u w=2u
M1 VDD vb1 vout VDD PMOS l=0.18u w=4u
VDD VDD 0 1.8
Cload vout 0 1p
.model NMOS NMOS
.model PMOS PMOS
.lib /Users/kesvis/Library/Application Support/LTspice/lib/cmp/standard.mos
.backanno
.end

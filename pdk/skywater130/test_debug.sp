* Debug wrdata
.option scale=1.0u
.param sky130_fd_pr__nfet_01v8__toxe_slope = 0
.param sky130_fd_pr__nfet_01v8__vth0_slope = 0  
.param sky130_fd_pr__nfet_01v8__vth0_slope1 = 0
.param sky130_fd_pr__nfet_01v8__voff_slope = 0
.param sky130_fd_pr__nfet_01v8__nfactor_slope = 0
.param sky130_fd_pr__nfet_01v8__lint_diff = 0
.param sky130_fd_pr__nfet_01v8__wint_diff = 0

.include cells/nfet_01v8/sky130_fd_pr__nfet_01v8__tt.corner.spice

Vdd vdd 0 DC 1.8
Vss vss 0 DC 0
Vgs vgs 0 DC 0.6

XM1 vdd vgs vss vss sky130_fd_pr__nfet_01v8 L=0.5 W=1 nf=1

.control
dc Vgs 0 1.2 0.05
let id_val = abs(@xm1.msky130_fd_pr__nfet_01v8[id])
let gm_val = @xm1.msky130_fd_pr__nfet_01v8[gm]
let gmid_val = gm_val/id_val
print id_val > check.txt
echo "Wrote data with device params"
wrdata test_output.dat v(vgs) id_val gm_val gmid_val
quit
.endc
.end


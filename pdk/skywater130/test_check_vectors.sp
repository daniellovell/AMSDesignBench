* Check what vectors are available
.option scale=1.0u
.param sky130_fd_pr__nfet_01v8__toxe_slope = 0
.param sky130_fd_pr__nfet_01v8__vth0_slope = 0  
.param sky130_fd_pr__nfet_01v8__vth0_slope1 = 0
.param sky130_fd_pr__nfet_01v8__voff_slope = 0
.param sky130_fd_pr__nfet_01v8__nfactor_slope = 0
.param sky130_fd_pr__nfet_01v8__lint_diff = 0
.param sky130_fd_pr__nfet_01v8__wint_diff = 0

.include cells/nfet_01v8/sky130_fd_pr__nfet_01v8__tt.corner.spice

Vd vdd 0 DC 1.8
Vg vg 0 DC 0.6
Vs vs 0 DC 0

XM1 vdd vg vs vs sky130_fd_pr__nfet_01v8 L=0.5 W=1 nf=1

.control
dc Vg 0 1.2 0.05
print all
quit
.endc
.end


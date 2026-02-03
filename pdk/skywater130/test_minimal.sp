* Minimal SKY130 NMOS Test
* Try to use just the basic nfet_01v8 model directly

* Load only essential parameters
.option scale=1.0u
.option temp=27

* Define minimal required parameters
.param sky130_fd_pr__nfet_01v8__toxe_slope = 0
.param sky130_fd_pr__nfet_01v8__vth0_slope = 0  
.param sky130_fd_pr__nfet_01v8__vth0_slope1 = 0
.param sky130_fd_pr__nfet_01v8__voff_slope = 0
.param sky130_fd_pr__nfet_01v8__nfactor_slope = 0
.param sky130_fd_pr__nfet_01v8__lint_diff = 0
.param sky130_fd_pr__nfet_01v8__wint_diff = 0

* Include just the typical corner for nfet_01v8
.include cells/nfet_01v8/sky130_fd_pr__nfet_01v8__tt.corner.spice

* Test circuit
Vd vdd 0 DC 1.8
Vg vg 0 DC 0.6
Vs vs 0 DC 0

* Instantiate NFET using the subcircuit
XM1 vdd vg vs vs sky130_fd_pr__nfet_01v8 L=0.5 W=1 nf=1

.control
op
dc Vg 0 1.2 0.05
let id = abs(@xm1.msky130_fd_pr__nfet_01v8[id])
let gm = @xm1.msky130_fd_pr__nfet_01v8[gm]
let gmid = gm/id
wrdata test_minimal_results.txt vg id gm gmid
echo "Gm/ID sweep complete. Results saved to test_minimal_results.txt"
quit
.endc

.end


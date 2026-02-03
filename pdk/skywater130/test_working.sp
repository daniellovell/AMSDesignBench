* Working SKY130 Gm/ID Test
.option scale=1.0u

* Define required slope parameters
.param sky130_fd_pr__nfet_01v8__toxe_slope = 0
.param sky130_fd_pr__nfet_01v8__vth0_slope = 0  
.param sky130_fd_pr__nfet_01v8__vth0_slope1 = 0
.param sky130_fd_pr__nfet_01v8__voff_slope = 0
.param sky130_fd_pr__nfet_01v8__nfactor_slope = 0
.param sky130_fd_pr__nfet_01v8__lint_diff = 0
.param sky130_fd_pr__nfet_01v8__wint_diff = 0

* Include SKY130 NFET model
.include cells/nfet_01v8/sky130_fd_pr__nfet_01v8__tt.corner.spice

* Test circuit
Vdd vdd 0 DC 1.8
Vss vss 0 DC 0
Vgs vgs 0 DC 0.6

* NFET: Drain=vdd, Gate=vgs, Source=vss, Bulk=vss
XM1 vdd vgs vss vss sky130_fd_pr__nfet_01v8 L=0.5 W=1 nf=1

* Write results
.control
dc Vgs 0 1.2 0.05
let id_abs = abs(@xm1.msky130_fd_pr__nfet_01v8[id])
let gm_val = @xm1.msky130_fd_pr__nfet_01v8[gm]
let gmid = gm_val/id_abs
set wr_singlescale
set wr_vecnames
option numdgt=7
wrdata /Users/kesvis/justbedaniel_2/AMSDesignBench/pdk/skywater130/sky130_gmid_nfet.dat v(vgs) id_abs gm_val gmid
echo "SUCCESS: SKY130 Gm/ID data generated!"
quit
.endc

.end


* Testbench for Telescopic Cascode OTA (ota002)
* Design verification for AI-generated circuits

.title OTA002 Design Verification Testbench

* Options (must come before circuit elements)
.option scale=1.0u

* SKY130 PDK Models (define parameters for nominal simulation)
.param sky130_fd_pr__nfet_01v8__toxe_slope = 0
.param sky130_fd_pr__nfet_01v8__toxe_slope1 = 0
.param sky130_fd_pr__nfet_01v8__vth0_slope = 0  
.param sky130_fd_pr__nfet_01v8__vth0_slope1 = 0
.param sky130_fd_pr__nfet_01v8__voff_slope = 0
.param sky130_fd_pr__nfet_01v8__voff_slope1 = 0
.param sky130_fd_pr__nfet_01v8__nfactor_slope = 0
.param sky130_fd_pr__nfet_01v8__nfactor_slope1 = 0
.param sky130_fd_pr__nfet_01v8__lint_diff = 0
.param sky130_fd_pr__nfet_01v8__wint_diff = 0
.param sky130_fd_pr__nfet_01v8__wlod_diff = 0
.param sky130_fd_pr__nfet_01v8__kvth0_diff = 0
.param sky130_fd_pr__nfet_01v8__llodvth_diff = 0
.param sky130_fd_pr__nfet_01v8__lkvth0_diff = 0
.param sky130_fd_pr__nfet_01v8__wkvth0_diff = 0
.param sky130_fd_pr__nfet_01v8__ku0_diff = 0
.param sky130_fd_pr__nfet_01v8__lku0_diff = 0
.param sky130_fd_pr__nfet_01v8__wku0_diff = 0
.param sky130_fd_pr__nfet_01v8__pku0_diff = 0
.param sky130_fd_pr__nfet_01v8__tku0_diff = 0
.param sky130_fd_pr__nfet_01v8__kvsat_diff = 0
.param sky130_fd_pr__nfet_01v8__llodku0_diff = 0
.param sky130_fd_pr__nfet_01v8__wlodku0_diff = 0
.param sky130_fd_pr__nfet_01v8__kvth0_slope = 0

.param sky130_fd_pr__pfet_01v8__toxe_slope = 0
.param sky130_fd_pr__pfet_01v8__toxe_slope1 = 0
.param sky130_fd_pr__pfet_01v8__vth0_slope = 0  
.param sky130_fd_pr__pfet_01v8__vth0_slope1 = 0
.param sky130_fd_pr__pfet_01v8__voff_slope = 0
.param sky130_fd_pr__pfet_01v8__voff_slope1 = 0
.param sky130_fd_pr__pfet_01v8__nfactor_slope = 0
.param sky130_fd_pr__pfet_01v8__nfactor_slope1 = 0
.param sky130_fd_pr__pfet_01v8__lint_diff = 0
.param sky130_fd_pr__pfet_01v8__wint_diff = 0
.param sky130_fd_pr__pfet_01v8__wlod_diff = 0
.param sky130_fd_pr__pfet_01v8__kvth0_diff = 0
.param sky130_fd_pr__pfet_01v8__llodvth_diff = 0
.param sky130_fd_pr__pfet_01v8__lkvth0_diff = 0
.param sky130_fd_pr__pfet_01v8__wkvth0_diff = 0
.param sky130_fd_pr__pfet_01v8__ku0_diff = 0
.param sky130_fd_pr__pfet_01v8__lku0_diff = 0
.param sky130_fd_pr__pfet_01v8__wku0_diff = 0
.param sky130_fd_pr__pfet_01v8__pku0_diff = 0
.param sky130_fd_pr__pfet_01v8__tku0_diff = 0
.param sky130_fd_pr__pfet_01v8__kvsat_diff = 0
.param sky130_fd_pr__pfet_01v8__llodku0_diff = 0
.param sky130_fd_pr__pfet_01v8__wlodku0_diff = 0
.param sky130_fd_pr__pfet_01v8__kvth0_slope = 0

* Include SKY130 models (relative paths from PDK root where ngspice runs)
.include cells/nfet_01v8/sky130_fd_pr__nfet_01v8__tt.corner.spice
.include cells/pfet_01v8/sky130_fd_pr__pfet_01v8__tt.corner.spice

* Global parameters (temperature for simulation)
.param TEMP=27

* Supply voltage (VDD provided by DUT netlist)
VDD vdd 0 DC 1.8
VSS vss 0 DC 0

* Load capacitors (CL value provided by DUT netlist, differential outputs)
CLP voutp 0 10p
CLN voutn 0 10p

* ===== DUT (Design Under Test) =====
* DUT provides:
*   - Input voltage sources Vinp, Vinn with designed DC common-mode
*   - Four bias voltage sources (Vb1, Vb2, Vb3, Vtail)
*   - Transistor parameters and circuit topology
* This section will be replaced with AI-generated netlist
{dut_netlist}
* ===== End of DUT =====

* ==== Measurements ====
.control
* Run DC operating point analysis first
op
echo "DC Operating Point Analysis Complete"

* Run AC analysis for gain, GBW, phase margin
ac dec 100 1 1G

* AC Analysis Measurements
set units=degrees

* Differential output (voutp - voutn)
let vout_diff = v(voutp) - v(voutn)
let vout_diff_mag = abs(vout_diff)
let vout_diff_db = db(vout_diff_mag)
let vout_diff_phase = phase(vout_diff)

* Find DC Gain (low frequency)
meas ac dc_gain_db find vout_diff_db at=10

* Find Unity Gain Frequency (0dB crossing)
meas ac unity_gain_freq_hz when vout_diff_db=0 cross=1

* Find Phase Margin at UGF
meas ac phase_at_ugf find vout_diff_phase when vout_diff_db=0 cross=1

* Power Measurement (from DC operating point)
let power_w = 1.8 * abs(vdd#branch)

echo ""
echo "=== BENCHMARK RESULTS ==="
print phase_at_ugf
print unity_gain_freq_hz
print dc_gain_db
print power_w
echo ""

quit
.endc

.end

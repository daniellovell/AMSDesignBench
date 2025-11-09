* Testbench for Gainboost Cascode OTA (ota009)

.title OTA009 Design Verification Testbench

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

.include cells/nfet_01v8/sky130_fd_pr__nfet_01v8__tt.corner.spice
.include cells/pfet_01v8/sky130_fd_pr__pfet_01v8__tt.corner.spice

.param TEMP=27

VDD vdd 0 DC 1.8
VSS vss 0 DC 0

* Load capacitor(s)
CL vout 0 5p

* ===== DUT (Design Under Test) =====
* DUT provides input sources, bias voltages, and circuit topology
{dut_netlist}
* ===== End of DUT =====

.control
op
let power_w = 1.8 * abs(i(vdd))
print power_w > {output_file}
echo "DC Operating Point Analysis Complete"

ac dec 100 1 1G
set units=degrees

* Single-ended output (try common names)
if length(v(vout)) > 0
  let output_node = v(vout)
else
  if length(v(out)) > 0
    let output_node = v(out)
  else
    let output_node = v(n2)
  end
end

let vout_mag = abs(output_node)
let vout_db = db(vout_mag)
let vout_phase = phase(output_node)

meas ac dc_gain_db find vout_db at=10
meas ac unity_gain_freq_hz when vout_db=0 cross=1
meas ac phase_at_ugf find vout_phase when vout_db=0 cross=1


echo ""
echo "=== BENCHMARK RESULTS ==="
print phase_at_ugf
print unity_gain_freq_hz
print dc_gain_db
echo ""

quit
.endc

.end

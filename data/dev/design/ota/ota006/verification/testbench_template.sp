* Testbench for Telescopic HS SE OTA (ota006)

.title OTA006 Design Verification Testbench

.option scale=1.0u
.option savecurrents

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
CL vout 0 10p

* ===== DUT (Design Under Test) =====
* DUT provides input sources, bias voltages, and circuit topology
{dut_netlist}
* ===== End of DUT =====

.control
op
* Power Measurement: P = V * I for all voltage sources
* VDD power (positive current flows out of positive terminal)
* Robust power measurement (current through VDD source)
let i_vdd = -i(vdd)
let power_w = v(vdd) * i_vdd
print power_w
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

* Determine input signal (prefer differential vip-vin / vinp-vinn)
if length(v(vip)) > 0 & length(v(vin)) > 0
  let input_node = v(vip) - v(vin)
else
  if length(v(vinp)) > 0 & length(v(vinn)) > 0
    let input_node = v(vinp) - v(vinn)
  else
    if length(v(vin)) > 0
      let input_node = v(vin)
    else
      * Fallback: assume 1V input to avoid divide-by-zero
      let input_node = 1
    end
  end
end

* Small-signal gain (V/V)
let gain = output_node / input_node
let gain_mag = abs(gain)
let vout_db = db(gain_mag)
let vout_phase = phase(gain)

meas ac dc_gain_db find vout_db at=10
meas ac unity_gain_freq_hz when vout_db=0 cross=1
meas ac phase_at_ugf find vout_phase when vout_db=0 cross=1

* Phase margin: only valid if unity_gain_freq_hz was found
if length(phase_at_ugf) > 0
  let phase_margin_deg = 180 + phase_at_ugf
else
  let phase_margin_deg = -1
end


echo ""
echo "=== BENCHMARK RESULTS ==="
print power_w
print phase_margin_deg
print phase_at_ugf
print unity_gain_freq_hz
print dc_gain_db
echo ""

quit
.endc

.end

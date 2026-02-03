* feedback001 verification testbench (TIA with resistive feedback)
.title feedback001 verification
.option savecurrents

* Provide a simple single-pole op-amp macromodel with parameters Aol and GBW.
* Implementation: EGAIN with DC gain Aol, then a 1-ohm/ Cdom dominant pole at fp=GBW/Aol.
.subckt opamp in_n in_p out Aol=100k GBW=10Meg
EGAIN nint 0 in_p in_n {{Aol}}
RDOM nint out 1
CDOM out 0 {{Aol/(6.283185307179586*GBW)}}
.ends opamp

* ===== DUT (Design Under Test) =====
{dut_netlist}
* ===== End of DUT =====

* Drive: 1 A AC current into the summing node
IIN S_in 0 DC 0 AC 1

.control
ac dec 200 1 100Meg
set units=degrees

* For AC=1A current, V(out) magnitude is transimpedance in Ohms
let z = v(S_out)
let z_mag = abs(z)
let z_db = db(z_mag)

meas ac transimpedance_ohm find z_mag at=10
meas ac dc_transimpedance_db find z_db at=10

* -3dB bandwidth relative to 10 Hz magnitude
meas ac bandwidth_hz when z_db=(dc_transimpedance_db-3) cross=1

echo ""
echo "=== BENCHMARK RESULTS ==="
print transimpedance_ohm
print bandwidth_hz
echo ""

quit
.endc
.end



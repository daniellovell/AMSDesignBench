* feedback002 verification testbench (TIA with capacitive feedback)
.title feedback002 verification
.option savecurrents

.subckt opamp in_n in_p out Aol=100k GBW=10Meg
EGAIN nint 0 in_p in_n {{Aol}}
RDOM nint out 1
CDOM out 0 {{Aol/(6.283185307179586*GBW)}}
.ends opamp

* ===== DUT (Design Under Test) =====
{dut_netlist}
* ===== End of DUT =====

IIN S_in 0 DC 0 AC 1

.control
ac dec 200 1 100Meg
set units=degrees

let z = v(S_out)
let z_mag = abs(z)
let z_db = db(z_mag)

* Measure transimpedance magnitude at a midband frequency (10 kHz) to avoid DC singularity for integrator
meas ac transimpedance_ohm find z_mag at=10k

* -3dB bandwidth relative to 10 kHz magnitude (where |Z| begins to depart due to op-amp limits)
meas ac mid_transimpedance_db find z_db at=10k
meas ac bandwidth_hz when z_db=(mid_transimpedance_db-3) cross=1

echo ""
echo "=== BENCHMARK RESULTS ==="
print transimpedance_ohm
print bandwidth_hz
echo ""

quit
.endc
.end



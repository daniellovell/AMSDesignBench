* feedback004 verification testbench (inverting amplifier)
.title feedback004 verification
.option savecurrents

.subckt opamp in_n in_p out Aol=100k GBW=10Meg
EGAIN nint 0 in_p in_n {{Aol}}
RDOM nint out 1
CDOM out 0 {{Aol/(6.283185307179586*GBW)}}
.ends opamp

* ===== DUT (Design Under Test) =====
{dut_netlist}
* ===== End of DUT =====

VIN S_in 0 DC 0 AC 1

.control
ac dec 200 1 100Meg
set units=degrees

let gain = v(S_out)/v(S_in)
let gain_mag = abs(gain)
let gain_db = db(gain_mag)

meas ac gain_vv find gain_mag at=10
meas ac dc_gain_db find gain_db at=10
meas ac bandwidth_hz when gain_db=(dc_gain_db-3) cross=1

echo ""
echo "=== BENCHMARK RESULTS ==="
print gain_vv
print bandwidth_hz
echo ""

quit
.endc
.end



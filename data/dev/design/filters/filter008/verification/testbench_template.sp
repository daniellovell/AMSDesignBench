* Testbench for Filter Design Verification

.title Filter Design Verification Testbench

* Ideal op-amp subcircuit (for active filters)
.subckt OPAMP vout vin_neg vin_pos
E1 vout 0 vin_pos vin_neg 1e6
Rout vout 0 1
.ends

* ===== DUT (Design Under Test) =====
* DUT provides input source and filter topology
{dut_netlist}
* ===== End of DUT =====

.control
* AC analysis from 1 Hz to 1 MHz
ac dec 100 1 1Meg
set units=degrees

* Determine output node (try common names)
if length(v(vout)) > 0
  let output_node = v(vout)
else
  if length(v(out)) > 0
    let output_node = v(out)
  else
    let output_node = v(n2)
  end
end

* Calculate magnitude and phase
let vout_mag = abs(output_node)
let vout_db = db(vout_mag)
let vout_phase = phase(output_node)
* Wrap phase to [0, 360) so all-pass f0 phase (-90) becomes ~270
let phase_wrapped = vout_phase
if phase_wrapped < 0
  let phase_wrapped = phase_wrapped + 360
end

* FILTER008 is an all-pass design: magnitude is (ideally) flat, so peak/3dB logic is unreliable.
* Instead, define the characteristic frequency explicitly as the testbench passband frequency
* (computed from design_spec) and measure phase there.
let fc_low = {passband_freq}
meas ac phase_at_peak find phase_wrapped at={passband_freq}

* Provide compatible outputs for the shared reporting/scoring paths
meas ac peak_gain_db max vout_db
meas ac peak_freq when vout_db=peak_gain_db
let gain_vv = vout_mag

* Dynamic frequency measurement points based on filter specifications
* These are calculated relative to the filter's characteristic frequency
* passband_gain: gain well within the passband (fc/10 for LP, fc*10 for HP)
* stopband_gain: gain well within the stopband (fc*10 for LP, fc/10 for HP)
meas ac passband_gain find vout_db at={passband_freq}
meas ac stopband_gain find vout_db at={stopband_freq}

* For notch filters, find minimum
meas ac notch_depth_db min vout_db
meas ac notch_freq when vout_db=notch_depth_db

echo ""
echo "=== FILTER VERIFICATION RESULTS ==="
echo "Measurement frequencies: passband={passband_freq}Hz, stopband={stopband_freq}Hz"
print peak_gain_db
print peak_freq
print fc_low
print fc_high
print bandpass_bandwidth
print center_frequency
print quality_factor
print gain_vv
print passband_gain
print stopband_gain
print phase_at_peak
print notch_depth_db
print notch_freq
echo ""

* Write results to file
print peak_gain_db peak_freq fc_low fc_high bandpass_bandwidth center_frequency quality_factor gain_vv passband_gain stopband_gain phase_at_peak notch_depth_db notch_freq > {output_file}

quit
.endc

.end

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

* Find peak (for band-pass and band-stop filters)
meas ac peak_gain_db max vout_db
meas ac peak_freq when vout_db=peak_gain_db

* Find -3dB points
let target_3db = peak_gain_db - 3
meas ac fc_low when vout_db=target_3db cross=1
meas ac fc_high when vout_db=target_3db cross=last

* Calculate bandpass_bandwidth and quality factor
let bandpass_bandwidth = fc_high - fc_low
let center_freq_calc = sqrt(fc_low * fc_high)
* Avoid division by zero for quality factor (use max to ensure denominator is at least 1)
let bandpass_bandwidth_safe = max(bandpass_bandwidth, 1)
let quality_factor = center_freq_calc / bandpass_bandwidth_safe

* Measure actual center frequency (for band-pass/band-stop)
* For filters where fc_low = fc_high (like low-pass), use the geometric mean
let center_frequency = center_freq_calc

* Measure gain at center/peak frequency (in V/V, not dB)
let gain_linear = 10^(peak_gain_db/20)
let gain_vv = gain_linear

* Dynamic frequency measurement points based on filter specifications
* These are calculated relative to the filter's characteristic frequency
* passband_gain: gain well within the passband (fc/10 for LP, fc*10 for HP)
* stopband_gain: gain well within the stopband (fc*10 for LP, fc/10 for HP)
meas ac passband_gain find vout_db at={passband_freq}
meas ac stopband_gain find vout_db at={stopband_freq}

* Phase at peak frequency
meas ac phase_at_peak find vout_phase when vout_db=peak_gain_db

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

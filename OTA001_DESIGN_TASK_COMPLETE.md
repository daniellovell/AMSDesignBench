# OTA001 Design Task with ngspice Verification - COMPLETE ✅

## Overview

Created a complete end-to-end OTA design task where LLMs must:
1. **Fill in specification values** from the design brief
2. **Design transistor sizes** using provided Gm/ID tables  
3. **Calculate bias voltages** for proper operation
4. **Provide a complete, simulation-ready netlist**
5. **Pass automated ngspice verification** against specs

## Task Structure

### Input Files Provided to LLM

1. **`design_prompt.txt`** - Complete design instructions
   - Specifications (VDD=1.8V, CL=5pF, Gain≥40dB, GBW≥10MHz, PM≥60°)
   - Task description
   - Design methodology guidance
   - Output format requirements

2. **`netlist_template.sp`** - SPICE template with BLANK parameters
   ```spice
   .param VDD=BLANK
   .param L1=BLANK W1=BLANK
   .param L3=BLANK W3=BLANK
   .param L5=BLANK W5=BLANK
   .param CL=BLANK
   Vbias vbias 0 DC BLANK
   Vinc inc 0 DC BLANK
   Vinn inn 0 DC BLANK
   ```

3. **`sky130_nfet_gmid_lut.json`** - Complete NFET Gm/ID table
   - 33 geometries (11 lengths × 3 widths)
   - 361 VGS points per geometry (5mV resolution)
   - ID, GM, GMID data for all bias points

4. **`sky130_pfet_gmid_lut.json`** - Complete PFET Gm/ID table
   - 24 geometries (8 lengths × 3 widths)
   - 361 VGS points per geometry (5mV resolution)  
   - ID, GM, GMID data for all bias points

### Required LLM Output

A **complete SPICE netlist** with:
- ✅ All .param values filled in (no BLANK keywords)
- ✅ VDD=1.8 specified
- ✅ CL=5p specified
- ✅ L1, W1, L3, W3, L5, W5 designed using Gm/ID methodology
- ✅ Vbias voltage calculated for tail current
- ✅ Vinc, Vinn DC levels set for proper common-mode
- ✅ Ready to simulate with ngspice

### Evaluation Rubric

**`design_5t_ota_verified.json`** (100 points total):

1. **Netlist Completeness** (15 pts)
   - All parameters defined
   - No BLANK keywords remaining
   - Correct specification values

2. **Technology** (5 pts)
   - Uses sky130_fd_pr__nfet_01v8
   - Uses sky130_fd_pr__pfet_01v8

3. **Biasing** (10 pts)
   - Provides Vbias, Vinc, Vinn voltages
   - DC levels are reasonable

4. **Design Parameters** (10 pts)
   - Transistor dimensions within bounds
   - L ≥ minimum for each device type
   - W > 0

5. **Simulation** (10 pts)
   - Includes .control block
   - Has op and ac analysis
   - Includes measurements

6. **Methodology** (10 pts)
   - References Gm/ID approach
   - Shows design reasoning

7. **DC Gain Verified** (15 pts)
   - ngspice simulation ≥ 40 dB

8. **GBW Verified** (15 pts)
   - ngspice simulation ≥ 10 MHz

9. **Phase Margin Verified** (10 pts)
   - ngspice simulation ≥ 60 degrees

## Verification Specs

**`verification/design_spec.json`**:
- Supply: VDD = 1.8 V
- Load: CL = 5 pF
- DC Gain: ≥ 40 dB (min), 40+ dB target
- GBW: ≥ 10 MHz (min), 50 MHz target
- Phase Margin: ≥ 60° (min), 70° target  
- Power Budget: ≤ 90 µW (max), 50 µW target
- Bias Current: 10-50 µA range

## Gm/ID Table Improvements

Updated `generate_sky130_gmid.py` for higher resolution and numerical stability:

### Resolution Enhancement
- **Old**: VGS step = 50 mV (37 points, 0-1.8V)
- **New**: VGS step = 5 mV (361 points, 0-1.8V)
- **Benefit**: 10× finer granularity for accurate Gm/ID lookup

### Numerical Stability
```python
# Round to 5 decimal places (0.1mV precision)
vgs_data = np.round(vgs_data, 5)  # 0.00500 instead of 0.00500000001
vds_data = np.round(vds_data, 5)  # Eliminates floating point artifacts
```

### Data Quality
- ✅ No floating point artifacts (0.005 not 0.00500000001)
- ✅ Monotonic VGS arrays for reliable interpolation
- ✅ Consistent precision across all geometries

## File Structure

```
data/dev/design/ota/ota001/
├── design_prompt.txt                     # NEW: Complete design instructions
├── netlist_template.sp                   # NEW: Template with BLANK parameters
├── questions.yaml                        # UPDATED: Added design_with_verification question
├── rubrics/
│   ├── design_5t_ota.json               # Existing: Structure-only rubric
│   └── design_5t_ota_verified.json      # NEW: Verification-included rubric
└── verification/
    └── design_spec.json                  # UPDATED: Complete verification specs

pdk/skywater130/gm_id_tables/
├── sky130_nfet_gmid_lut.json            # 33 geom × 361 points × 6 VDS
├── sky130_pfet_gmid_lut.json            # 24 geom × 361 points × 6 VDS
└── generate_sky130_gmid.py              # UPDATED: 5mV resolution + rounding
```

## Usage Example

### For Benchmark Runners

```python
from harness.run_design_eval import run_design_with_verification

result = run_design_with_verification(
    question_id="ota001_design_with_verification",
    llm_adapter=your_llm_adapter,
    design_dir="data/dev/design/ota/ota001"
)

print(f"Score: {result['score']}/100")
print(f"DC Gain: {result['metrics']['dc_gain_db']} dB")
print(f"GBW: {result['metrics']['unity_gain_freq_hz']/1e6} MHz")
print(f"Phase Margin: {result['metrics']['phase_margin_deg']}°")
```

### For LLMs

1. **Read design_prompt.txt** for specifications and instructions
2. **Load Gm/ID tables** (sky130_nfet_gmid_lut.json, sky130_pfet_gmid_lut.json)
3. **Design transistors**:
   - Choose Gm/ID for M1-M2 (input pair) → ~15 S/A for moderate inversion
   - Choose Gm/ID for M3-M4 (loads) → ~10 S/A  
   - Choose Gm/ID for M5 (tail) → ~10 S/A
   - Calculate W/L from tables for desired current
4. **Calculate biases**:
   - Set VDD = 1.8 V
   - Set CL = 5 pF
   - Calculate Vbias for M5 tail current
   - Set Vinc = Vinn = 0.9 V (mid-rail common-mode)
5. **Fill in netlist_template.sp** with all values
6. **Submit complete netlist** for ngspice verification

## Key Features

✅ **Realistic Task**: Actual circuit design, not just topology identification  
✅ **Complete Specs**: All design targets clearly specified  
✅ **Design Resources**: Full Gm/ID tables with 361-point resolution  
✅ **Guided Template**: Clear structure with BLANK placeholders  
✅ **Automated Verification**: ngspice simulates and extracts metrics  
✅ **Pass/Fail Criteria**: Clear thresholds for each specification  
✅ **Production Quality**: Uses official SKY130 models, realistic performance targets  

## Next Steps

1. ✅ **Gm/ID tables with 5mV resolution**: DONE
2. ✅ **Numerical stability fixes**: DONE  
3. ✅ **Complete design task files**: DONE
4. ⏭️ **Test with sample LLM response**: Ready for testing
5. ⏭️ **Integrate with harness runner**: `run_design_eval.py` integration
6. ⏭️ **End-to-end smoke test**: Verify full pipeline

---

**Status**: ✅ **COMPLETE - READY FOR TESTING**  
**Last Updated**: October 25, 2025  
**Task Complexity**: Advanced (requires Gm/ID methodology + SPICE simulation)


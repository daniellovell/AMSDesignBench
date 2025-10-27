# Running the OTA001 Design Task

## Quick Start

Run this command to see task details and usage instructions:

```bash
cd /Users/kesvis/justbedaniel_2/AMSDesignBench
source ../venv/bin/activate
python3 test_ota001_design.py
```

## Task Overview

**Design Challenge**: Design a 5-transistor operational transconductance amplifier (OTA) using the SkyWater 130nm PDK.

**Specifications**:
- Supply Voltage: 1.8 V
- Load Capacitance: 5 pF
- DC Gain: ≥ 40 dB
- Unity Gain Frequency (GBW): ≥ 10 MHz
- Phase Margin: ≥ 60 degrees
- Power Budget: ≤ 90 µW
- Bias Current Range: 10-50 µA

## What the LLM Receives

The LLM is provided with:

1. **Design Prompt** (`data/dev/design/ota/ota001/design_prompt.txt`)
   - Complete specifications
   - Design methodology guidance
   - Output format requirements

2. **Netlist Template** (`data/dev/design/ota/ota001/netlist_template.sp`)
   - SPICE structure with BLANK parameters to fill in
   - Example:
     ```spice
     .param VDD=BLANK
     .param L1=BLANK W1=BLANK
     Vbias vbias 0 DC BLANK
     ```

3. **NFET Gm/ID Table** (`pdk/skywater130/gm_id_tables/sky130_nfet_gmid_lut.json`)
   - 33 geometries (11 lengths × 3 widths)
   - 71,478 data points (5mV VGS resolution)
   - ID, GM, GMID for all bias conditions

4. **PFET Gm/ID Table** (`pdk/skywater130/gm_id_tables/sky130_pfet_gmid_lut.json`)
   - 24 geometries (8 lengths × 3 widths)
   - 51,984 data points (5mV VGS resolution)
   - ID, GM, GMID for all bias conditions

## What the LLM Must Provide

A complete SPICE netlist with:

✅ All `.param` values filled in (no BLANK keywords)  
✅ VDD = 1.8 V specified  
✅ CL = 5 pF specified  
✅ Transistor dimensions (L1, W1, L3, W3, L5, W5) designed using Gm/ID methodology  
✅ Bias voltages (Vbias, Vinc, Vinn) calculated for proper operation  
✅ Ready to simulate with ngspice (includes .control, op, ac analysis)

## Evaluation (100 points total)

### Static Checks (50 points)
- **Netlist Completeness** (15 pts): All parameters defined, no BLANK keywords
- **Technology** (5 pts): Uses `sky130_fd_pr__nfet_01v8` and `sky130_fd_pr__pfet_01v8`
- **Biasing** (10 pts): Provides Vbias, Vinc, Vinn voltages
- **Design Parameters** (10 pts): Transistor dimensions within bounds (L ≥ min, W > 0)
- **Simulation** (10 pts): Includes .control block, op and ac analysis, measurements

### Verified Performance (40 points)
- **DC Gain** (15 pts): ngspice simulation shows ≥ 40 dB
- **GBW** (15 pts): ngspice simulation shows ≥ 10 MHz
- **Phase Margin** (10 pts): ngspice simulation shows ≥ 60 degrees

### Design Reasoning (10 points)
- **Methodology** (10 pts): References Gm/ID approach, shows design reasoning

## Running Options

### Option 1: Test Mode (Check Task Setup)

```bash
python3 test_ota001_design.py
```

This will:
- ✅ Verify all files are present
- ✅ Load Gm/ID tables
- ✅ Display task specifications
- ✅ Show usage instructions

### Option 2: Manual LLM Testing (Python API)

```python
from pathlib import Path
import json
from harness.adapters import anthropic  # or openai

# Load task materials
ota001_dir = Path("data/dev/design/ota/ota001")
pdk_dir = Path("pdk/skywater130")

# Read files
with open(ota001_dir / "design_prompt.txt") as f:
    prompt = f.read()

with open(ota001_dir / "netlist_template.sp") as f:
    template = f.read()

with open(pdk_dir / "gm_id_tables/sky130_nfet_gmid_lut.json") as f:
    nfet_table = json.load(f)

with open(pdk_dir / "gm_id_tables/sky130_pfet_gmid_lut.json") as f:
    pfet_table = json.load(f)

# Call LLM
adapter = anthropic.build(model="claude-3-5-sonnet-20241022")
context = f"""
{prompt}

NETLIST TEMPLATE:
{template}

NFET Gm/ID TABLE:
{json.dumps(nfet_table, indent=2)}

PFET Gm/ID TABLE:
{json.dumps(pfet_table, indent=2)}
"""

response = adapter.generate(context)
print(response)

# Verify and score (see below for verification code)
```

### Option 3: Automated Evaluation Runner

```bash
# Run design evaluation with a specific model
python3 harness/run_design_eval.py --model gpt-4 --designs ota001

# Or test with dummy LLM
python3 harness/run_design_eval.py --model dummy --designs ota001

# Run all OTA designs
python3 harness/run_design_eval.py --model claude-3.5-sonnet
```

Results will be saved to `outputs/design_run_TIMESTAMP/`

## Verifying the Design

After getting the LLM's netlist, verify it with ngspice:

```python
from harness.design_verification import NetlistParser, SpiceRunner, DesignJudge
from pathlib import Path
import json

# 1. Parse netlist
parser = NetlistParser()
netlist = parser.extract_netlist(llm_response)
parsed = parser.parse(netlist)

if not parsed.is_valid:
    print(f"Invalid netlist: {parsed.errors}")
    exit(1)

# 2. Run SPICE simulation
pdk_path = Path("pdk/skywater130")
output_dir = Path("outputs/test_run")
runner = SpiceRunner(pdk_path, output_dir)

with open("data/dev/design/ota/ota001/verification/design_spec.json") as f:
    spec = json.load(f)

results = runner.run_simulation(parsed.cleaned_netlist, spec, "ota001")

if not results.success:
    print(f"Simulation failed: {results.errors}")
    exit(1)

print(f"DC Gain: {results.metrics['dc_gain_db']} dB")
print(f"GBW: {results.metrics['unity_gain_freq_hz']/1e6} MHz")
print(f"Phase Margin: {results.metrics['phase_margin_deg']} degrees")

# 3. Judge the design
judge = DesignJudge(adapter)
judgment = judge.evaluate(results.metrics, spec, parsed.cleaned_netlist)

print(f"\nScore: {judgment.score}/100")
print(f"Pass: {judgment.overall_pass}")

for spec_name, spec_result in judgment.spec_results.items():
    status = "✓" if spec_result['pass'] else "✗"
    print(f"  {status} {spec_name}: {spec_result['message']}")
```

## File Structure

```
data/dev/design/ota/ota001/
├── design_prompt.txt              # Complete design instructions
├── netlist_template.sp            # SPICE template with BLANK parameters
├── questions.yaml                 # Question metadata
├── rubrics/
│   ├── design_5t_ota.json        # Structure-only rubric
│   └── design_5t_ota_verified.json  # With verification (NEW)
└── verification/
    └── design_spec.json           # Design specifications for verification

pdk/skywater130/
├── models/
│   └── sky130.lib.spice          # SKY130 SPICE models
└── gm_id_tables/
    ├── sky130_nfet_gmid_lut.json  # NFET Gm/ID data
    ├── sky130_pfet_gmid_lut.json  # PFET Gm/ID data
    └── generate_sky130_gmid.py    # Table generator
```

## Regenerating Gm/ID Tables (if needed)

If you need to regenerate the Gm/ID tables with updated resolution:

```bash
cd /Users/kesvis/justbedaniel_2/AMSDesignBench
source ../venv/bin/activate
python3 pdk/skywater130/gm_id_tables/generate_sky130_gmid.py
```

This will:
- Characterize NFET devices (33 geometries, 5mV VGS steps)
- Characterize PFET devices (24 geometries, 5mV VGS steps)
- Save tables to `pdk/skywater130/gm_id_tables/`
- Takes ~5-10 minutes to complete

## Troubleshooting

### "Gm/ID table not found"

Run the table generation script:
```bash
python3 pdk/skywater130/gm_id_tables/generate_sky130_gmid.py
```

### "ngspice not found"

Install ngspice:
```bash
# macOS
brew install ngspice

# Linux (Ubuntu/Debian)
sudo apt-get install ngspice
```

### "SKY130 models not found"

The PDK models should be in `pdk/skywater130/cells/`. If missing, they were downloaded during setup. Check:
```bash
ls pdk/skywater130/cells/nfet_01v8/
ls pdk/skywater130/cells/pfet_01v8/
```

### "Module not found" errors

Ensure you've activated the virtual environment:
```bash
source ../venv/bin/activate
```

## Next Steps

1. ✅ **Verify Setup**: Run `python3 test_ota001_design.py`
2. 🔄 **Test with Dummy LLM**: `python3 harness/run_design_eval.py --model dummy --designs ota001`
3. 🚀 **Run with Real LLM**: Configure API keys and run with `--model gpt-4` or `--model claude-3.5-sonnet`

## Example LLM Response Format

The LLM should respond with something like:

```
I'll design a 5-transistor OTA to meet the specifications using the Gm/ID methodology.

**Design Approach:**
- Target Gm/ID ≈ 15 S/A for input pair (moderate inversion)
- Target Gm/ID ≈ 10 S/A for loads and tail
- Bias current: 30 µA total (15 µA per branch)

**SPICE Netlist:**

```spice
* Five-Transistor OTA Design
.lib /Users/kesvis/justbedaniel_2/AMSDesignBench/pdk/skywater130/models/sky130.lib.spice tt

.param VDD=1.8
.param CL=5p
.param L1=0.5u W1=8u
.param L3=0.5u W3=15u
.param L5=1u W5=6u
.param IBIAS=30u

Vdd vdd 0 DC 1.8
Vss vss 0 DC 0
Vbias vbias 0 DC 0.55
Vinp inp inc AC 0.5
Vinc inc 0 DC 0.9
Vinn inn 0 DC 0.9

XM1 out1 inp vtail vss sky130_fd_pr__nfet_01v8 L={L1} W={W1} nf=1
XM2 out2 inn vtail vss sky130_fd_pr__nfet_01v8 L={L1} W={W1} nf=1
XM3 out1 out1 vdd vdd sky130_fd_pr__pfet_01v8 L={L3} W={W3} nf=1
XM4 out2 out1 vdd vdd sky130_fd_pr__pfet_01v8 L={L3} W={W3} nf=1
XM5 vtail vbias vss vss sky130_fd_pr__nfet_01v8 L={L5} W={W5} nf=1

CL out2 0 {CL}

.control
op
ac dec 100 1 1g
...
.endc
.end
```

**Expected Performance:**
- DC Gain: ~48 dB
- GBW: ~25 MHz
- Phase Margin: ~68°
- Power: ~54 µW
```

---

**Status**: ✅ Ready to use  
**Last Updated**: October 25, 2025  
**Contact**: For issues, check `test_ota001_design.py` output


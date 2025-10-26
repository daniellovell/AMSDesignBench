# Design Verification System

Automated SPICE-based verification of AI-generated OTA designs using ngspice and LLM-based judging.

## Overview

The design verification system extends AMSDesignBench to evaluate LLMs' ability to design analog circuits (not just analyze them). It includes:

1. **Gm/ID Lookup Tables**: Pre-characterized transistor performance data
2. **SPICE Simulation**: Automated ngspice simulation of LLM-generated designs
3. **LLM-Based Judging**: Intelligent evaluation of simulation results against specs
4. **Automated Scoring**: Weighted scoring based on specification compliance

## Architecture

```
┌─────────────────┐
│  LLM Model      │
│  (Design)       │
└────────┬────────┘
         │ SPICE Netlist
         ▼
┌─────────────────┐
│ Netlist Parser  │
│ (Extract/Valid) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ SPICE Runner    │
│ (ngspice)       │
└────────┬────────┘
         │ Metrics
         ▼
┌─────────────────┐
│ Design Judge    │
│ (LLM + Rules)   │
└────────┬────────┘
         │
         ▼
    Score & Report
```

## Directory Structure

```
AMSDesignBench/
├── pdk/
│   └── skywater130/
│       ├── models/              # PDK SPICE models
│       │   ├── nfet_01v8.pm3.spice
│       │   └── pfet_01v8.pm3.spice
│       └── gm_id_tables/        # Gm/ID lookup tables
│           ├── generate_gmid_tables.py
│           ├── gmid_helper.py
│           ├── nfet_gmid_lut.json
│           └── pfet_gmid_lut.json
│
├── data/dev/design/ota/
│   └── ota001/
│       └── verification/
│           ├── design_spec.json         # Specifications
│           └── testbench_template.sp    # SPICE testbench
│
└── harness/
    ├── design_verification/
    │   ├── netlist_parser.py    # Extract netlists from LLM
    │   ├── spice_runner.py      # Run ngspice simulations
    │   └── design_judge.py      # Judge results vs specs
    └── run_design_eval.py       # Main evaluation script
```

## Setup

### 1. Install Dependencies

```bash
# Install ngspice
# macOS:
brew install ngspice

# Linux:
sudo apt-get install ngspice

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Setup PDK (Optional but Recommended)

For accurate simulations, download the SkyWater 130nm PDK models:

```bash
cd pdk/skywater130/models
# Download from https://github.com/google/skywater-pdk
# Place nfet_01v8.pm3.spice and pfet_01v8.pm3.spice here
```

**Note**: Placeholder Gm/ID tables are included for testing. For production use, generate real tables:

```bash
cd pdk/skywater130/gm_id_tables
python generate_gmid_tables.py
```

### 3. Verify Installation

```bash
# Test ngspice
ngspice --version

# Test Python imports
python -c "from harness.design_verification import NetlistParser, SpiceRunner, DesignJudge"
```

## Usage

### Running Design Evaluation

Basic usage:

```bash
python harness/run_design_eval.py --model openai:gpt-4o-mini
```

Advanced options:

```bash
python harness/run_design_eval.py \
    --model anthropic:claude-3-5-sonnet-latest \
    --designs ota001 ota002 \
    --output outputs/my_design_run \
    --pdk-path pdk/skywater130
```

### Command-Line Options

- `--model MODEL`: LLM model to evaluate (required)
- `--config PATH`: Path to bench_config.yaml (default: bench_config.yaml)
- `--output PATH`: Output directory (default: outputs/design_run_TIMESTAMP)
- `--pdk-path PATH`: Path to PDK (default: pdk/skywater130)
- `--designs ID [ID ...]`: Specific design IDs to test (default: all)

### Example Output

```
Starting design evaluation for gpt-4o-mini
PDK: /path/to/pdk/skywater130
Output: outputs/design_run_20240125_143022
------------------------------------------------------------
Found 3 design test cases

[1/3] Evaluating ota001...
  → Requesting design from LLM...
  → Parsing netlist...
  → Running SPICE simulation...
  → Evaluating against specifications...
  ✓ Score: 82.5/100 - PASS

[2/3] Evaluating ota002...
  → Requesting design from LLM...
  → Parsing netlist...
  → Running SPICE simulation...
  → Evaluating against specifications...
  ✗ Score: 58.3/100 - FAIL

[3/3] Evaluating ota004...
  → Requesting design from LLM...
  → Parsing netlist...
  → Running SPICE simulation...
  → Evaluating against specifications...
  ✓ Score: 75.0/100 - PASS

Evaluation complete! Results saved to outputs/design_run_20240125_143022
```

## Design Specifications

Each OTA test case includes a `design_spec.json` file that defines:

### Required Fields

```json
{
  "design_id": "ota001",
  "topology": "five_transistor_ota",
  "description": "5-Transistor OTA with NMOS differential pair",
  
  "pdk": {
    "technology": "sky130",
    "supply_voltage": 1.8,
    "temperature": 27
  },
  
  "specifications": {
    "dc_gain": {
      "min": 40,
      "target": 60,
      "unit": "dB",
      "weight": 0.25
    },
    "gbw": {
      "min": 10e6,
      "target": 50e6,
      "unit": "Hz",
      "weight": 0.20
    },
    "phase_margin": {
      "min": 55,
      "target": 65,
      "unit": "deg",
      "weight": 0.20
    }
    // ... more specs
  },
  
  "test_conditions": {
    "load_capacitance": "10p",
    "feedback_factor": 1.0,
    "input_common_mode": 0.9
  },
  
  "constraints": {
    "min_transistor_length": 150e-9,
    "min_transistor_width": 300e-9
  }
}
```

### Specification Format

Each specification entry can include:
- `min`: Minimum acceptable value
- `max`: Maximum acceptable value
- `target`: Target/optimal value
- `unit`: Units (dB, Hz, V, W, etc.)
- `weight`: Relative weight for scoring (0-1)
- `note`: Optional note about the specification

## Scoring System

### Rule-Based Scoring

1. **Pass/Fail**: Each specification checked against min/max bounds
2. **Weighted Score**: Specifications weighted by importance
3. **Partial Credit**: Given for near-misses based on margin

### Score Calculation

```python
spec_score = 100  # if passed

# Bonus for exceeding target
if margin > 10% of target:
    spec_score = min(110, 100 + margin_pct / 10)

# Partial credit if failed
if failed:
    spec_score = max(0, 50 - margin_pct)

total_score = sum(spec_score * weight) / sum(weights)
```

### LLM Judge

The LLM judge provides:
- **Reasoning**: Why specs passed/failed
- **Trade-off Analysis**: Power vs. speed, gain vs. bandwidth
- **Recommendations**: Specific design improvements

## Results Format

### JSON Output

`{model}_design_results.json`:

```json
{
  "model": "gpt-4o-mini",
  "timestamp": "2024-01-25T14:30:22",
  "pdk": "/path/to/pdk",
  "results": [
    {
      "design_id": "ota001",
      "status": "pass",
      "score": 82.5,
      "topology": "five_transistor_ota",
      "llm_response": "...",
      "netlist": "...",
      "simulation": {
        "success": true,
        "metrics": {
          "dc_gain_db": 45.2,
          "gbw_hz": 52e6,
          "phase_margin_deg": 62.3,
          "power_w": 235e-6
        }
      },
      "judgment": {
        "overall_pass": true,
        "score": 82.5,
        "spec_results": {
          "dc_gain": {
            "pass": true,
            "value": 45.2,
            "target": 60,
            "margin": 5.2
          }
          // ... more specs
        },
        "reasoning": "Design successfully meets all minimum specifications...",
        "recommendations": []
      }
    }
  ]
}
```

### Text Report

`{model}_design_report.txt`:

```
Design Verification Report
============================================================
Model: gpt-4o-mini
Timestamp: 2024-01-25T14:30:22
Total test cases: 3

Summary:
  Passed: 2/3
  Failed: 1/3
  Errors: 0/3
  Average Score: 71.9/100

Detailed Results:
------------------------------------------------------------

Design: ota001
Status: pass
Score: 82.5/100
Specifications:
  ✓ dc_gain: Pass (value: 45.2, target: 60)
  ✓ gbw: Pass (value: 52MHz, target: 50MHz)
  ✓ phase_margin: Pass (value: 62.3deg, target: 65deg)
  ✓ power: Pass (value: 235uW, max: 500uW)
  ...
```

## Gm/ID Tables

### Overview

Gm/ID tables provide pre-characterized transistor performance for various operating points:
- **Gm/ID**: Transconductance efficiency (S/A)
- **ft**: Transit frequency
- **gm/gds**: Intrinsic gain

### Using Gm/ID Tables

```python
from pdk.skywater130.gm_id_tables.gmid_helper import load_pdk_tables

nfet_lut, pfet_lut = load_pdk_tables(pdk_path)

# Query for specific operating point
op_point = nfet_lut.query(L=500e-9, gmid=12, vds=0.9)
# Returns: {vgs, id, gm, gds, vth, ft, gm_gds}

# Size transistor for target Gm
W = nfet_lut.get_width_for_gm(L=500e-9, gm_target=100e-6, gmid=12)

# Complete sizing for target current
sizing = nfet_lut.get_sizing(L=500e-9, id_target=50e-6, gmid=10)
# Returns: {W, L, vgs, gm, id, vth, vdsat}
```

### Generating Tables

With actual PDK models installed:

```bash
cd pdk/skywater130/gm_id_tables
python generate_gmid_tables.py --output-dir . --pdk-path ..
```

This sweeps VGS, VDS, and L to generate comprehensive lookup tables.

## Troubleshooting

### Common Issues

**1. ngspice not found**
```bash
# Install ngspice
brew install ngspice  # macOS
sudo apt-get install ngspice  # Linux
```

**2. PDK models not found**
```
Warning: Models directory not found
```
Solution: Either download real PDK models or use placeholder tables (works for testing)

**3. Simulation timeout**
```
Error: Simulation timed out after 60 seconds
```
Solution: Increase timeout in `bench_config.yaml` or check netlist for issues

**4. Invalid netlist**
```
Status: invalid_netlist
```
Solution: Check LLM output format. Netlist should be in proper SPICE syntax

**5. Metric not found**
```
Metric 'dc_gain_db' not found in simulation results
```
Solution: Check testbench template includes proper measurement commands

### Debug Mode

Add verbose output to see detailed simulation logs:

```bash
# Set environment variable
export DESIGN_VERIFY_DEBUG=1

python harness/run_design_eval.py --model gpt-4o-mini
```

## Extending the System

### Adding New Design Types

1. Create design specification in `data/dev/design/{type}/{id}/verification/design_spec.json`
2. Create testbench template `testbench_template.sp`
3. Add topology-specific measurements to testbench
4. Update `DesignEvaluator._discover_design_cases()` if needed

### Custom Specifications

Add new specification types to `design_spec.json`:

```json
{
  "specifications": {
    "slew_rate": {
      "min": 5e6,
      "unit": "V/s",
      "weight": 0.10
    },
    "settling_time": {
      "max": 100e-9,
      "unit": "s",
      "weight": 0.10
    }
  }
}
```

Update testbench to measure these specs.

### Custom PDKs

To use a different PDK:

1. Create `pdk/{pdk_name}/` directory
2. Add models to `pdk/{pdk_name}/models/`
3. Generate Gm/ID tables with appropriate device names
4. Update `bench_config.yaml` to point to new PDK

## Performance Tips

1. **Parallel Evaluation**: Run multiple models simultaneously
2. **Cache Results**: Simulation results are saved per design
3. **Selective Testing**: Use `--designs` to test specific cases
4. **Mock Mode**: Use placeholder tables for faster iteration

## Citation

If you use this design verification system in research, please cite:

```bibtex
@software{amsdesignbench_design_verification,
  title = {AMSDesignBench Design Verification System},
  author = {Your Name},
  year = {2024},
  url = {https://github.com/yourusername/AMSDesignBench}
}
```

## License

Same as AMSDesignBench main project.

## Support

- **Issues**: https://github.com/yourusername/AMSDesignBench/issues
- **Discussions**: https://github.com/yourusername/AMSDesignBench/discussions

## Acknowledgments

- SkyWater PDK: https://github.com/google/skywater-pdk
- ngspice: http://ngspice.sourceforge.net/
- Gm/ID methodology: Boris Murmann's design toolbox


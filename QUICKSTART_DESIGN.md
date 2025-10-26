# Quick Start: Design Verification

Get up and running with AI-driven OTA design verification in 5 minutes.

## Prerequisites

- Python 3.8+
- ngspice installed
- LLM API keys (OpenAI, Anthropic, etc.)

## Installation

```bash
# 1. Install ngspice
# macOS:
brew install ngspice

# Linux:
sudo apt-get install ngspice

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Set up API keys
export OPENAI_API_KEY="your-key-here"
export ANTHROPIC_API_KEY="your-key-here"
```

## Quick Test

Run a simple design evaluation:

```bash
# Activate virtual environment if using one
source venv/bin/activate

# Run design verification
python harness/run_design_eval.py --model openai:gpt-4o-mini --designs ota001
```

Expected output:
```
Starting design evaluation for gpt-4o-mini
Found 1 design test cases

[1/1] Evaluating ota001...
  → Requesting design from LLM...
  → Parsing netlist...
  → Running SPICE simulation...
  → Evaluating against specifications...
  ✓ Score: 82.5/100 - PASS

Evaluation complete!
```

## Understanding Results

Results are saved in `outputs/design_run_TIMESTAMP/`:

```
outputs/design_run_20240125_143022/
├── gpt-4o-mini_design_results.json  # Detailed JSON results
├── gpt-4o-mini_design_report.txt    # Human-readable report
└── simulations/                      # SPICE simulation files
    └── ota001/
        ├── ota001_tb.sp             # Testbench netlist
        ├── results.txt              # Extracted metrics
        └── plots/                   # Performance plots
```

### JSON Results

```json
{
  "design_id": "ota001",
  "status": "pass",
  "score": 82.5,
  "simulation": {
    "metrics": {
      "dc_gain_db": 45.2,
      "gbw_hz": 52000000,
      "phase_margin_deg": 62.3,
      "power_w": 0.000235
    }
  },
  "judgment": {
    "spec_results": {
      "dc_gain": {"pass": true, "value": 45.2},
      "gbw": {"pass": true, "value": 52000000},
      "phase_margin": {"pass": true, "value": 62.3},
      "power": {"pass": true, "value": 0.000235}
    },
    "reasoning": "Design successfully meets all specifications..."
  }
}
```

### Text Report

```
Design Verification Report
============================================================

Summary:
  Passed: 1/1
  Average Score: 82.5/100

Detailed Results:
------------------------------------------------------------

Design: ota001
Status: pass
Score: 82.5/100
Specifications:
  ✓ dc_gain: Pass (45.2 dB)
  ✓ gbw: Pass (52 MHz)
  ✓ phase_margin: Pass (62.3°)
  ✓ power: Pass (235 µW)
```

## Next Steps

### 1. Test Multiple Models

```bash
python harness/run_design_eval.py --model openai:gpt-4o
python harness/run_design_eval.py --model anthropic:claude-3-5-sonnet-latest
```

### 2. Test All OTA Designs

```bash
python harness/run_design_eval.py --model openai:gpt-4o-mini
# Automatically discovers all OTA designs with verification specs
```

### 3. Add Custom Designs

Create a new design test case:

```bash
mkdir -p data/dev/design/ota/ota005/verification
```

Add `design_spec.json`:
```json
{
  "design_id": "ota005",
  "topology": "folded_cascode",
  "pdk": {
    "technology": "sky130",
    "supply_voltage": 1.8
  },
  "specifications": {
    "dc_gain": {"min": 60, "unit": "dB", "weight": 0.3},
    "gbw": {"min": 100e6, "unit": "Hz", "weight": 0.3},
    "power": {"max": 1e-3, "unit": "W", "weight": 0.2},
    "phase_margin": {"min": 55, "unit": "deg", "weight": 0.2}
  },
  "test_conditions": {
    "load_capacitance": "10p",
    "input_common_mode": 0.9
  }
}
```

Add `testbench_template.sp` (see existing examples).

### 4. Generate Real Gm/ID Tables

With actual PDK models:

```bash
cd pdk/skywater130/gm_id_tables
python generate_gmid_tables.py
```

## Common Workflows

### Development/Testing
```bash
# Use placeholder tables, test single design
python harness/run_design_eval.py \
    --model openai:gpt-4o-mini \
    --designs ota001
```

### Production Evaluation
```bash
# Use real PDK models, test all designs, multiple models
for model in "openai:gpt-4o" "anthropic:claude-3-5-sonnet-latest" "openai:gpt-4o-mini"; do
    python harness/run_design_eval.py \
        --model "$model" \
        --output "outputs/production_run_$(date +%Y%m%d)"
done
```

### Continuous Integration
```bash
# Quick verification on PR
python harness/run_design_eval.py \
    --model openai:gpt-4o-mini \
    --designs ota001 ota002 \
    --output ci_results
```

## Troubleshooting

### ngspice not found
```bash
which ngspice  # Should show path
ngspice --version  # Should show version
```

If not found, install:
```bash
# macOS
brew install ngspice

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install ngspice

# From source
wget https://sourceforge.net/projects/ngspice/files/ng-spice-rework/39/ngspice-39.tar.gz
tar -xzf ngspice-39.tar.gz
cd ngspice-39
./configure --prefix=/usr/local
make
sudo make install
```

### API Key Issues
```bash
# Check if keys are set
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY

# Set temporarily
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# Set permanently (add to ~/.bashrc or ~/.zshrc)
echo 'export OPENAI_API_KEY="sk-..."' >> ~/.bashrc
```

### Simulation Fails
1. Check netlist format in LLM response
2. Verify PDK models are accessible
3. Increase timeout in `bench_config.yaml`
4. Check simulation directory for error logs

### Import Errors
```bash
# Ensure you're in the project root
cd AMSDesignBench

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"

# Install missing dependencies
pip install -r requirements.txt
```

## Configuration

Edit `bench_config.yaml` to customize:

```yaml
design_verification:
  enabled: true
  pdk:
    name: skywater130
    path: pdk/skywater130
  simulation:
    engine: ngspice
    timeout_s: 120  # Increase if simulations timeout
  eval:
    max_tokens: 2000
    temperature: 0.3
```

## Tips

1. **Start Small**: Test one design with one model first
2. **Check Logs**: Review simulation output in `outputs/.../simulations/`
3. **Iterate**: Adjust specifications and rerun
4. **Compare Models**: Use same designs across different LLMs
5. **Monitor Costs**: Design generation uses more tokens than analysis

## Resources

- [Full Documentation](DESIGN_VERIFICATION_README.md)
- [Example Designs](data/dev/design/ota/)
- [Testbench Templates](data/dev/design/ota/ota001/verification/)
- [Gm/ID Helper](pdk/skywater130/gm_id_tables/gmid_helper.py)

## Getting Help

1. Check [DESIGN_VERIFICATION_README.md](DESIGN_VERIFICATION_README.md)
2. Review example outputs in `outputs/`
3. Inspect simulation logs for errors
4. Open an issue on GitHub

Happy designing! 🎨⚡


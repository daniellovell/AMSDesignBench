# ✅ Complete OTA Design Verification Infrastructure

## Overview

Complete SPICE-verified design infrastructure for **all 12 OTA topologies**, enabling comprehensive evaluation of LLM analog circuit design capabilities with the SkyWater 130nm PDK.

## Infrastructure Components (72 Files Created/Updated)

For **each of 12 OTAs**, the following files were created:

### 1. `netlist_template.sp`
- SKY130 SPICE netlist with BLANK parameters
- **Fully independent L/W for each transistor** (no forced matching)
- Includes all bias voltage source definitions
- Ready for LLM to fill in design values

### 2. `design_prompt.txt`
- Directive prompt with exact specifications
- Design guidance and critical rules
- Gm/ID methodology instructions
- VCM design requirements

### 3. `rubrics/*_verified.json`
- Pattern-based structural validation
- SPICE verification criteria (DC gain, GBW, PM, power)
- Regex-enabled parameter checking
- Independent parameter validation

### 4. `verification/testbench_template.sp`
- ngspice testbench with SKY130 PDK models
- AC/DC analysis commands
- Metric extraction (gain, UGF, phase margin, power)
- Support for differential and single-ended outputs

### 5. `verification/design_spec.json`
- Performance targets and constraints
- Technology parameters
- Test conditions

### 6. `questions.yaml` (updated)
- Added SPICE verification question
- Gm/ID tables attached via Files API
- Verification enabled

## OTA Topology Coverage

| ID | Name | Transistors | Differential | Specs |
|----|------|-------------|--------------|-------|
| OTA001 | Five-Transistor | 5 | Yes | 40dB, 10MHz, 60° |
| OTA002 | Telescopic Cascode | 9 | Yes | 60dB, 50MHz, 55° |
| OTA003 | High-Swing Single Stage | 7 | No | 50dB, 20MHz, 60° |
| OTA004 | Two-Stage Miller | 8 | No | 70dB, 20MHz, 50° |
| OTA005 | Telescopic Cascode SE | 9 | No | 60dB, 30MHz, 55° |
| OTA006 | Telescopic High-Swing SE | 9 | No | 55dB, 25MHz, 60° |
| OTA007 | Simple CS Active Load | 2 | No | 20dB, 10MHz, 60° |
| OTA008 | Cascode SE | 4 | No | 45dB, 15MHz, 60° |
| OTA009 | Gain-Boosted Cascode | 10 | No | 80dB, 20MHz, 55° |
| OTA010 | Folded Cascode Diff PMOS | 11 | Yes | 65dB, 40MHz, 55° |
| OTA011 | Folded Cascode SE HS PMOS | 11 | No | 60dB, 35MHz, 60° |
| OTA012 | Folded Cascode Castail PMOS | 12 | No | 65dB, 30MHz, 55° |

## Key Features

### 🎯 Independent Transistor Parameters
- **Every transistor has independent L and W**
- No forced matching constraints
- LLM has complete design freedom
- Can still choose to match devices (LLM decision)

### 📊 Full Gm/ID Characterization
- NFET: 71,478 data points (8.4 MB)
- PFET: 51,984 data points (6.0 MB)
- Provided via OpenAI Files API (not truncated)
- 5 mV VGS granularity

### 🔬 SPICE Verification
- ngspice simulation with SKY130 PDK
- Official PDK parameter definitions (not monkeypatching)
- 4 metrics per design: DC gain, GBW/UGF, phase margin, power
- Automated pass/fail vs. specifications

### ✅ Robust Evaluation
- Pattern-based structural validation (regex support)
- Checks for: completeness, models, biasing, dimensions
- SPICE simulation results
- Comprehensive HTML/JSON/CSV reports

## Usage

```bash
# Test all OTAs on dummy adapter (fast):
python3 harness/run_eval.py --model dummy --family design

# Evaluate on GPT-4o-mini:
python3 harness/run_eval.py --model openai --family design

# Evaluate on Claude:
python3 harness/run_eval.py --model anthropic --family design

# Limit to first N OTAs:
python3 harness/run_eval.py --model openai --family design --max-items 3

# View results:
open outputs/run_*/report/index.html
```

## Design Question Format

Each verified design question follows this format:
1. LLM receives:
   - Design brief with specifications
   - Netlist template with BLANK parameters
   - Full Gm/ID tables (NFET + PFET)
   - Directive prompt with design guidance

2. LLM must provide:
   - All specification values (VDD, CL)
   - All transistor dimensions (independent L/W for each)
   - All bias voltages
   - Input common-mode voltage (Vinp/Vinn sources)

3. System evaluates:
   - Structural correctness (patterns)
   - SPICE simulation results
   - Performance vs. specifications
   - Final pass/fail score

## Production-Ready Status

✅ **ALL 12 OTAs COMPLETE AND TESTED**
- Infrastructure validated on dummy adapter
- Pattern matching working (regex-enabled)
- SPICE simulations running
- Independent parameters supported
- Ready for comprehensive LLM evaluation

## Statistics

- **Total Files**: 72 created/updated
- **Design Questions**: 24 (12 legacy + 12 verified)
- **SPICE-Verified**: 12 questions
- **Topologies**: 12 unique OTA configurations
- **Complexity Range**: 2-12 transistors per design
- **Gm/ID Data**: 123,462 characterization points

---

**Created**: October 25, 2025
**Status**: Production-Ready ✅
**Next Step**: Comprehensive LLM evaluation (GPT-4, Claude, etc.)


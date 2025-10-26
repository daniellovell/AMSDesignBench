#!/usr/bin/env python3
"""
Comprehensive OTA infrastructure generator.
Creates all design verification files for OTA004-012.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any

BASE_DIR = Path(__file__).parent.parent

# Complete OTA specifications
OTA_CONFIGS = {
    "ota004": {
        "name": "Two-Stage Miller",
        "topology": "two_stage_miller",
        "differential": False,
        "specs": {"vdd": 1.8, "cl": "20p", "gain": 70, "gbw": 20e6, "pm": 50, "power": 1e-3},
        "has_comp_cap": True,
    },
    "ota005": {
        "name": "Telescopic Cascode Single-Ended",
        "topology": "telescopic_cascode_se",
        "differential": False,
        "specs": {"vdd": 1.8, "cl": "10p", "gain": 60, "gbw": 30e6, "pm": 55, "power": 0.8e-3},
    },
    "ota006": {
        "name": "Telescopic High-Swing SE",
        "topology": "telescopic_hs_se",
        "differential": False,
        "specs": {"vdd": 1.8, "cl": "10p", "gain": 55, "gbw": 25e6, "pm": 60, "power": 0.7e-3},
    },
    "ota007": {
        "name": "Simple CS with Active Load",
        "topology": "cs_active_load",
        "differential": False,
        "specs": {"vdd": 1.8, "cl": "5p", "gain": 20, "gbw": 10e6, "pm": 60, "power": 0.5e-3},
    },
    "ota008": {
        "name": "Cascode Single-Ended",
        "topology": "cascode_se",
        "differential": False,
        "specs": {"vdd": 1.8, "cl": "5p", "gain": 45, "gbw": 15e6, "pm": 60, "power": 0.6e-3},
    },
    "ota009": {
        "name": "Gain-Boosted Cascode",
        "topology": "gainboost_cascode",
        "differential": False,
        "specs": {"vdd": 1.8, "cl": "5p", "gain": 80, "gbw": 20e6, "pm": 55, "power": 1.2e-3},
    },
    "ota010": {
        "name": "Folded Cascode Diff PMOS",
        "topology": "folded_cascode_diff_pmos",
        "differential": True,
        "specs": {"vdd": 1.8, "cl": "10p", "gain": 65, "gbw": 40e6, "pm": 55, "power": 1e-3},
    },
    "ota011": {
        "name": "Folded Cascode SE High-Swing PMOS",
        "topology": "folded_cascode_se_hs_pmos",
        "differential": False,
        "specs": {"vdd": 1.8, "cl": "10p", "gain": 60, "gbw": 35e6, "pm": 60, "power": 0.9e-3},
    },
    "ota012": {
        "name": "Folded Cascode Cascoded-Tail PMOS",
        "topology": "folded_cascode_castail_pmos",
        "differential": False,
        "specs": {"vdd": 1.8, "cl": "10p", "gain": 65, "gbw": 30e6, "pm": 55, "power": 1e-3},
    },
}

def convert_netlist_to_sky130_template(ref_netlist: str, ota_id: str, config: Dict) -> str:
    """Convert reference LTSpice netlist to SKY130 template with BLANK parameters."""
    
    lines = []
    lines.append(f"* {config['name']} OTA Design Template for SKY130 PDK")
    lines.append("* Fill in all BLANK parameters based on specifications")
    lines.append("")
    lines.append("* Specifications (MUST fill in exact values from design brief):")
    lines.append(".param VDD=BLANK")
    lines.append(".param CL=BLANK")
    lines.append("")
    
    # Parse reference netlist to extract unique transistor types and create parameter groups
    transistor_params = set()
    ref_lines = ref_netlist.strip().split('\n')
    
    # Extract unique L/W combinations from reference
    for line in ref_lines:
        if line.strip() and line[0] in 'Mm':
            # Extract L and W values
            l_match = re.search(r'[Ll]=(\S+)', line)
            w_match = re.search(r'[Ww]=(\S+)', line)
            if l_match and w_match:
                transistor_params.add((l_match.group(1), w_match.group(1)))
    
    lines.append("* Transistor dimensions (DESIGN using Gm/ID tables):")
    lines.append("* Group similar transistors by function")
    lines.append(".param L1=BLANK W1=BLANK")  # Generic - LLM will determine grouping
    lines.append("")
    
    if config.get("has_comp_cap"):
        lines.append("* Miller compensation capacitor:")
        lines.append(".param Cc=BLANK")
        lines.append("")
    
    # Input sources
    lines.append("* Input voltage sources (DESIGN the DC common-mode voltage):")
    if config["differential"]:
        lines.append("Vinp vinp 0 DC BLANK AC 0.5")
        lines.append("Vinn vinn 0 DC BLANK AC -0.5")
    else:
        lines.append("Vin vin 0 DC BLANK AC 1.0")
    lines.append("")
    
    # Bias voltages - extract from reference
    bias_nodes = set()
    for line in ref_lines:
        if line.strip().startswith('V') and not line.startswith('VDD'):
            parts = line.split()
            if len(parts) >= 2:
                bias_nodes.add(parts[0].lower())
    
    lines.append("* Bias voltages (DESIGN these for proper operation):")
    if bias_nodes:
        for bias in sorted(bias_nodes):
            if bias not in ['vdd', 'vicm', 'cload', 'vin+', 'vin-']:
                node = bias[1:] if bias.startswith('v') else bias
                lines.append(f"V{node} {node} 0 DC BLANK")
    else:
        lines.append("* Vbias vbias 0 DC BLANK  (add as needed)")
    lines.append("")
    
    # Convert device lines to SKY130
    lines.append(f"* {config['name']} Topology:")
    device_num = 1
    for line in ref_lines:
        stripped = line.strip()
        if stripped and stripped[0] in 'Mm':
            # Parse device line
            parts = stripped.split()
            if len(parts) >= 5:
                dev_name = parts[0]
                nodes = ' '.join(parts[1:5])
                
                # Determine device type
                if 'nch' in stripped.lower() or 'nmos' in stripped.lower():
                    model = "sky130_fd_pr__nfet_01v8"
                elif 'pch' in stripped.lower() or 'pmos' in stripped.lower():
                    model = "sky130_fd_pr__pfet_01v8"
                else:
                    model = "BLANK_MODEL"
                
                # Use parameter references
                lines.append(f"X{dev_name.upper()} {nodes} {model} L=L1 W=W1 nf=1")
                device_num += 1
    
    return '\n'.join(lines)

def generate_design_prompt(ota_id: str, config: Dict) -> str:
    """Generate design prompt."""
    
    s = config["specs"]
    diff_str = "differential" if config["differential"] else "single-ended"
    
    prompt = f"""**TASK:** Fill in ALL BLANK parameters in the provided SPICE netlist template.

**SPECIFICATIONS (use these EXACT values):**
- VDD = {s['vdd']} V
- CL = {s['cl']} {'(per output)' if config['differential'] else ''}
- Target: DC Gain ≥ {s['gain']} dB, GBW ≥ {s['gbw']/1e6:.0f} MHz, Phase Margin ≥ {s['pm']}°
- Power < {s['power']*1e3:.1f} mW
- Technology: SKY130 (NFET min L=0.15µm, PFET min L=0.35µm)

**TOPOLOGY: {config['name']} ({diff_str})**

**INSTRUCTIONS:**

1. **Fill in specifications**: VDD={s['vdd']}, CL={s['cl']}

2. **Design transistor sizes** using Gm/ID tables (Gm/ID ≈ 10-20 S/A)
   - **CRITICAL**: Write `L1=0.5` NOT `L1=0.5u` (no 'u' suffix)

3. **Choose input common-mode voltage** and fill in Vinp/Vinn (or Vin) sources

4. **Design all bias voltages** for proper operation
"""

    if config.get("has_comp_cap"):
        prompt += "\n5. **Design Miller compensation capacitor** (Cc, typically 1-5 pF)\n"

    prompt += """
**CRITICAL RULES:**
- ✅ Use exact spec values
- ✅ NO 'u' suffix on L/W
- ❌ Do NOT add .lib, .option, .control, .end, Vdd, Vss, CL lines
- ❌ Do NOT leave any BLANK

**OUTPUT:** Provide ONLY the filled-in SPICE netlist in a code block.
"""
    return prompt

# Generate files
print("\n" + "="*70)
print("GENERATING FILES...")
print("="*70)

files_created = 0
for ota_id, config in OTA_CONFIGS.items():
    design_dir = BASE_DIR / "data/dev/design/ota" / ota_id
    template_dir = BASE_DIR / "data/dev/templates/ota" / ota_id
    
    print(f"\n{ota_id}: {config['name']}")
    
    # Read reference netlist (handle different encodings)
    ref_file = template_dir / "netlist.sp"
    if ref_file.exists():
        try:
            ref_netlist = ref_file.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                ref_netlist = ref_file.read_text(encoding='utf-16')
            except Exception:
                ref_netlist = ref_file.read_text(encoding='latin-1')
        
        # Generate netlist template
        template = convert_netlist_to_sky130_template(ref_netlist, ota_id, config)
        out_file = design_dir / "netlist_template.sp"
        out_file.write_text(template)
        print(f"  ✅ Created {out_file.name}")
        files_created += 1
        
        # Generate design prompt
        prompt = generate_design_prompt(ota_id, config)
        prompt_file = design_dir / "design_prompt.txt"
        prompt_file.write_text(prompt)
        print(f"  ✅ Created {prompt_file.name}")
        files_created += 1

print(f"\n{'='*70}")
print(f"✅ Created {files_created} files!")
print(f"{'='*70}")
EOGEN


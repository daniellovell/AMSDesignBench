#!/usr/bin/env python3
"""
Simple test script to run the OTA001 design task.

This demonstrates how to:
1. Load the design prompt and Gm/ID tables
2. Send them to an LLM for design
3. Extract and verify the netlist with ngspice
4. Score the design against specifications
"""

import json
import sys
from pathlib import Path

# Add harness to path
sys.path.insert(0, str(Path(__file__).parent))

def load_design_task():
    """Load the OTA001 design task materials."""
    ota001_dir = Path(__file__).parent / "data" / "dev" / "design" / "ota" / "ota001"
    pdk_dir = Path(__file__).parent / "pdk" / "skywater130"
    
    print("=" * 70)
    print("OTA001 DESIGN TASK - Test Run")
    print("=" * 70)
    print()
    
    # 1. Load design prompt
    prompt_file = ota001_dir / "design_prompt.txt"
    if not prompt_file.exists():
        print(f"❌ Design prompt not found: {prompt_file}")
        return None
    
    with open(prompt_file, 'r') as f:
        prompt = f.read()
    
    print(f"✅ Loaded design prompt ({len(prompt)} chars)")
    
    # 2. Load netlist template
    template_file = ota001_dir / "netlist_template.sp"
    if not template_file.exists():
        print(f"❌ Netlist template not found: {template_file}")
        return None
    
    with open(template_file, 'r') as f:
        template = f.read()
    
    print(f"✅ Loaded netlist template ({len(template)} chars)")
    
    # 3. Load Gm/ID tables
    nfet_table_file = pdk_dir / "gm_id_tables" / "sky130_nfet_gmid_lut.json"
    pfet_table_file = pdk_dir / "gm_id_tables" / "sky130_pfet_gmid_lut.json"
    
    if not nfet_table_file.exists():
        print(f"⚠️  NFET Gm/ID table not found: {nfet_table_file}")
        print(f"   Run: cd pdk/skywater130/gm_id_tables && python3 generate_sky130_gmid.py")
        nfet_table = None
    else:
        with open(nfet_table_file, 'r') as f:
            nfet_table = json.load(f)
        nfet_geoms = len(nfet_table['data'])
        total_points = sum(len(g['VGS']) for g in nfet_table['data'])
        print(f"✅ Loaded NFET Gm/ID table: {nfet_geoms} geometries, {total_points:,} data points")
    
    if not pfet_table_file.exists():
        print(f"⚠️  PFET Gm/ID table not found: {pfet_table_file}")
        print(f"   Run: cd pdk/skywater130/gm_id_tables && python3 generate_sky130_gmid.py")
        pfet_table = None
    else:
        with open(pfet_table_file, 'r') as f:
            pfet_table = json.load(f)
        pfet_geoms = len(pfet_table['data'])
        total_points = sum(len(g['VGS']) for g in pfet_table['data'])
        print(f"✅ Loaded PFET Gm/ID table: {pfet_geoms} geometries, {total_points:,} data points")
    
    # 4. Load design spec
    spec_file = ota001_dir / "verification" / "design_spec.json"
    if not spec_file.exists():
        print(f"❌ Design spec not found: {spec_file}")
        return None
    
    with open(spec_file, 'r') as f:
        spec = json.load(f)
    
    print(f"✅ Loaded design specifications")
    
    # 5. Load rubric
    rubric_file = ota001_dir / "rubrics" / "design_5t_ota_verified.json"
    if not rubric_file.exists():
        print(f"❌ Rubric not found: {rubric_file}")
        return None
    
    with open(rubric_file, 'r') as f:
        rubric = json.load(f)
    
    print(f"✅ Loaded evaluation rubric ({len(rubric['criteria'])} criteria)")
    
    return {
        'prompt': prompt,
        'template': template,
        'nfet_table': nfet_table,
        'pfet_table': pfet_table,
        'spec': spec,
        'rubric': rubric,
        'paths': {
            'ota001_dir': ota001_dir,
            'pdk_dir': pdk_dir
        }
    }


def show_task_details(task_data):
    """Display task details for the user."""
    spec = task_data['spec']
    
    print()
    print("=" * 70)
    print("TASK OVERVIEW")
    print("=" * 70)
    print()
    print(f"Design ID: {spec['design_id']}")
    print(f"Topology: {spec['topology']}")
    print(f"Description: {spec['description']}")
    print()
    print("SPECIFICATIONS:")
    for spec_name, spec_def in spec['specifications'].items():
        if 'min' in spec_def:
            print(f"  • {spec_name}: ≥ {spec_def['min']} {spec_def['unit']}")
        if 'max' in spec_def:
            print(f"  • {spec_name}: ≤ {spec_def['max']} {spec_def['unit']}")
        if 'value' in spec_def:
            print(f"  • {spec_name}: {spec_def['value']} {spec_def['unit']}")
    print()
    print("EVALUATION CRITERIA:")
    total_weight = sum(c['weight'] for c in task_data['rubric']['criteria'])
    for criterion in task_data['rubric']['criteria']:
        print(f"  • {criterion['desc']} ({criterion['weight']:.0f} pts)")
    print(f"\nTotal Score: {total_weight:.0f} points")
    print()


def show_usage_instructions():
    """Show how to use this task with an LLM."""
    print("=" * 70)
    print("HOW TO USE THIS TASK")
    print("=" * 70)
    print()
    print("STEP 1: Prepare the LLM prompt")
    print("  Include:")
    print("  - design_prompt.txt (specifications and instructions)")
    print("  - netlist_template.sp (SPICE template with BLANK parameters)")
    print("  - sky130_nfet_gmid_lut.json (NFET Gm/ID table)")
    print("  - sky130_pfet_gmid_lut.json (PFET Gm/ID table)")
    print()
    print("STEP 2: Get LLM design")
    print("  The LLM should return a complete SPICE netlist with:")
    print("  - All .param values filled in (no BLANK keywords)")
    print("  - VDD=1.8 and CL=5p specified")
    print("  - L1, W1, L3, W3, L5, W5 designed using Gm/ID methodology")
    print("  - Vbias, Vinc, Vinn voltages calculated")
    print()
    print("STEP 3: Simulate with ngspice")
    print("  Run the netlist through ngspice to extract:")
    print("  - DC gain (dB)")
    print("  - Unity gain frequency (Hz)")
    print("  - Phase margin (degrees)")
    print()
    print("STEP 4: Score the design")
    print("  Use the rubric to evaluate:")
    print("  - Netlist completeness (15 pts)")
    print("  - Technology usage (5 pts)")
    print("  - Biasing (10 pts)")
    print("  - Reasonable dimensions (10 pts)")
    print("  - Simulation commands (10 pts)")
    print("  - Design methodology (10 pts)")
    print("  - DC Gain ≥ 40 dB (15 pts)")
    print("  - GBW ≥ 10 MHz (15 pts)")
    print("  - Phase Margin ≥ 60° (10 pts)")
    print()
    print("=" * 70)
    print()


def demonstrate_with_dummy_llm():
    """Show a simple example with a dummy LLM response."""
    print("=" * 70)
    print("EXAMPLE: Using with an LLM")
    print("=" * 70)
    print()
    print("To test with a real LLM (e.g., GPT-4, Claude):")
    print()
    print("  from harness.adapters import openai  # or anthropic")
    print("  adapter = openai.build(model='gpt-4')")
    print()
    print("  # Prepare context")
    print("  context = f'''")
    print("  {task_data['prompt']}")
    print()
    print("  NETLIST TEMPLATE:")
    print("  {task_data['template']}")
    print()
    print("  NFET Gm/ID TABLE: [attached as JSON file]")
    print("  PFET Gm/ID TABLE: [attached as JSON file]")
    print("  '''")
    print()
    print("  # Get design from LLM")
    print("  response = adapter.generate(context)")
    print()
    print("  # Parse and verify netlist")
    print("  from harness.design_verification import NetlistParser, SpiceRunner")
    print("  parser = NetlistParser()")
    print("  netlist = parser.extract_netlist(response)")
    print("  parsed = parser.parse(netlist)")
    print()
    print("  # Run SPICE simulation")
    print("  runner = SpiceRunner(pdk_path, output_dir)")
    print("  results = runner.run_simulation(parsed.cleaned_netlist, spec, 'ota001')")
    print()
    print("  # Score the design")
    print("  from harness.design_verification import DesignJudge")
    print("  judge = DesignJudge(adapter)")
    print("  judgment = judge.evaluate(results.metrics, spec, parsed.cleaned_netlist)")
    print()
    print("  print(f'Score: {judgment.score}/100')")
    print("  print(f'Pass: {judgment.overall_pass}')")
    print()


def main():
    """Main entry point."""
    print()
    
    # Load task
    task_data = load_design_task()
    if task_data is None:
        print()
        print("❌ Failed to load task. Please check the files and try again.")
        return 1
    
    # Show details
    show_task_details(task_data)
    
    # Show usage
    show_usage_instructions()
    
    # Show example
    demonstrate_with_dummy_llm()
    
    print("=" * 70)
    print("QUICK START COMMANDS")
    print("=" * 70)
    print()
    print("1. Generate Gm/ID tables (if not already done):")
    print("   cd /Users/kesvis/justbedaniel_2/AMSDesignBench")
    print("   source ../venv/bin/activate")
    print("   python3 pdk/skywater130/gm_id_tables/generate_sky130_gmid.py")
    print()
    print("2. Run automated design evaluation (when ready):")
    print("   python3 harness/run_design_eval.py --model gpt-4 --designs ota001")
    print()
    print("3. Test with dummy LLM:")
    print("   python3 harness/run_design_eval.py --model dummy --designs ota001")
    print()
    print("=" * 70)
    print()
    print("✅ Task loaded successfully!")
    print("   Files are ready in: data/dev/design/ota/ota001/")
    print("   Gm/ID tables in: pdk/skywater130/gm_id_tables/")
    print()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())


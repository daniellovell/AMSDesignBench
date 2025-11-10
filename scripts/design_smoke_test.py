#!/usr/bin/env python3
"""
Design Verification Smoke Test

Quick end-to-end test of the design verification system without requiring
actual LLM calls or SPICE simulations.
"""

import sys
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from harness.design_verification import NetlistParser, SimulationResults, JudgmentResult


def test_netlist_parser():
    """Test netlist extraction and parsing."""
    print("\n=== Testing Netlist Parser ===")
    
    parser = NetlistParser()
    
    # Test netlist extraction from markdown
    llm_response = """
Here's a simple 5-transistor OTA design:

```spice
* 5-Transistor OTA
M1 vout1 vin+ vtail 0 nfet W=10u L=1u
M2 vout2 vin- vtail 0 nfet W=10u L=1u
M3 vout1 vout1 vdd vdd pfet W=5u L=1u
M4 vout2 vout1 vdd vdd pfet W=5u L=1u
M5 vtail vbias 0 0 nfet W=20u L=1u
.end
```

This design uses a differential pair (M1, M2) with active loads (M3, M4).
"""
    
    netlist = parser.extract_netlist(llm_response)
    
    if netlist:
        print("✓ Successfully extracted netlist from LLM response")
        print(f"  Length: {len(netlist)} chars")
    else:
        print("✗ Failed to extract netlist")
        return False
    
    # Test parsing
    parsed = parser.parse(netlist)
    
    if parsed.is_valid:
        print("✓ Netlist is valid")
        print(f"  Devices: {len(parsed.devices)}")
        print(f"  Nodes: {len(parsed.nodes)}")
    else:
        print(f"✗ Netlist invalid: {parsed.errors}")
        return False
    
    return True


def test_simulation_results():
    """Test simulation results structure."""
    print("\n=== Testing Simulation Results ===")
    
    # Create mock simulation results
    results = SimulationResults(
        success=True,
        metrics={
            'dc_gain_db': 45.2,
            'gbw_hz': 52e6,
            'phase_margin_deg': 62.3,
            'power_w': 235e-6
        },
        warnings=[]
    )
    
    if results.success:
        print("✓ Simulation results structure valid")
        print(f"  Metrics: {len(results.metrics)}")
    else:
        print("✗ Simulation results invalid")
        return False
    
    # Test serialization
    results_dict = results.to_dict()
    if 'metrics' in results_dict and 'success' in results_dict:
        print("✓ Results serialization works")
    else:
        print("✗ Results serialization failed")
        return False
    
    return True


def test_design_spec_loading():
    """Test loading design specifications."""
    print("\n=== Testing Design Specification Loading ===")
    
    base_dir = Path(__file__).parent.parent
    spec_file = base_dir / "data" / "dev" / "design" / "ota" / "ota001" / "verification" / "design_spec.json"
    
    if not spec_file.exists():
        print(f"✗ Design spec not found: {spec_file}")
        return False
    
    try:
        with open(spec_file, 'r') as f:
            spec = json.load(f)
        
        required_keys = ['design_id', 'topology', 'specifications', 'pdk']
        missing = [k for k in required_keys if k not in spec]
        
        if missing:
            print(f"✗ Missing required keys: {missing}")
            return False
        
        print("✓ Design specification loaded successfully")
        print(f"  Design ID: {spec['design_id']}")
        print(f"  Topology: {spec['topology']}")
        print(f"  Specifications: {len(spec['specifications'])}")
        
        return True
        
    except Exception as e:
        print(f"✗ Failed to load design spec: {e}")
        return False


def test_pdk_structure():
    """Test PDK directory structure."""
    print("\n=== Testing PDK Structure ===")
    
    base_dir = Path(__file__).parent.parent
    pdk_dir = base_dir / "pdk" / "skywater130"
    
    required_files = [
        "gm_id_tables/nfet_gmid_lut_placeholder.json",
        "gm_id_tables/pfet_gmid_lut_placeholder.json",
        "gm_id_tables/gmid_helper.py",
    ]
    
    all_ok = True
    for rel_path in required_files:
        full_path = pdk_dir / rel_path
        if full_path.exists():
            print(f"✓ {rel_path}")
        else:
            print(f"✗ Missing: {rel_path}")
            all_ok = False
    
    # Test loading Gm/ID table
    try:
        gmid_file = pdk_dir / "gm_id_tables" / "nfet_gmid_lut_placeholder.json"
        with open(gmid_file, 'r') as f:
            lut = json.load(f)
        
        if 'device_type' in lut and 'data' in lut:
            print("✓ Gm/ID table structure valid")
        else:
            print("✗ Gm/ID table structure invalid")
            all_ok = False
            
    except Exception as e:
        print(f"✗ Failed to load Gm/ID table: {e}")
        all_ok = False
    
    return all_ok


def test_testbench_templates():
    """Test testbench template existence."""
    print("\n=== Testing Testbench Templates ===")
    
    base_dir = Path(__file__).parent.parent
    design_dir = base_dir / "data" / "dev" / "design" / "ota"
    
    found_templates = 0
    for ota_dir in design_dir.glob("ota*"):
        tb_file = ota_dir / "verification" / "testbench_template.sp"
        if tb_file.exists():
            found_templates += 1
            print(f"✓ {ota_dir.name}/verification/testbench_template.sp")
    
    if found_templates > 0:
        print(f"\n✓ Found {found_templates} testbench templates")
        return True
    else:
        print("✗ No testbench templates found")
        return False


def test_modules_import():
    """Test that all modules can be imported."""
    print("\n=== Testing Module Imports ===")
    
    try:
        from harness.design_verification import NetlistParser
        print("✓ NetlistParser imported")
    except ImportError as e:
        print(f"✗ Failed to import NetlistParser: {e}")
        return False
    
    try:
        from harness.design_verification import SpiceRunner
        print("✓ SpiceRunner imported")
    except ImportError as e:
        print(f"✗ Failed to import SpiceRunner: {e}")
        return False
    
    try:
        from harness.design_verification import DesignJudge
        print("✓ DesignJudge imported")
    except ImportError as e:
        print(f"✗ Failed to import DesignJudge: {e}")
        return False
    
    return True


def test_config():
    """Test configuration file."""
    print("\n=== Testing Configuration ===")
    
    import yaml
    
    base_dir = Path(__file__).parent.parent
    config_file = base_dir / "bench_config.yaml"
    
    if not config_file.exists():
        print("✗ bench_config.yaml not found")
        return False
    
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        if 'design_verification' in config:
            print("✓ Configuration includes design_verification section")
            dv_config = config['design_verification']
            print(f"  Enabled: {dv_config.get('enabled', False)}")
            print(f"  PDK: {dv_config.get('pdk', {}).get('name', 'N/A')}")
        else:
            print("⚠ Configuration missing design_verification section (optional)")
        
        return True
        
    except Exception as e:
        print(f"✗ Failed to load config: {e}")
        return False


def main():
    """Run all smoke tests."""
    print("\n" + "=" * 60)
    print("Design Verification Smoke Test")
    print("=" * 60)
    
    tests = [
        ("Module Imports", test_modules_import),
        ("Netlist Parser", test_netlist_parser),
        ("Simulation Results", test_simulation_results),
        ("Design Specs", test_design_spec_loading),
        ("PDK Structure", test_pdk_structure),
        ("Testbench Templates", test_testbench_templates),
        ("Configuration", test_config),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n✗ {test_name} crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n✓ All smoke tests passed!")
        print("\nNext steps:")
        print("  1. Install ngspice: brew install ngspice")
        print("  2. Set API keys: export OPENAI_API_KEY='...'")
        print("  3. Run full setup check: python scripts/verify_design_setup.py")
        print("  4. Run evaluation: python harness/run_design_eval.py --model openai:gpt-4o-mini --designs ota001")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())


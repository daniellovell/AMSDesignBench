#!/usr/bin/env python3
"""
Design Verification Setup Checker

Verifies that all components for design verification are properly installed
and configured.
"""

import sys
import subprocess
import json
from pathlib import Path
from typing import List, Tuple

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def check(name: str, passed: bool, message: str = ""):
    """Print check result."""
    if passed:
        print(f"{GREEN}✓{RESET} {name}")
        if message:
            print(f"  {message}")
    else:
        print(f"{RED}✗{RESET} {name}")
        if message:
            print(f"  {RED}{message}{RESET}")


def check_python_version() -> bool:
    """Check Python version."""
    version = sys.version_info
    required = (3, 8)
    passed = version >= required
    check(
        "Python Version",
        passed,
        f"Python {version.major}.{version.minor} (required: {required[0]}.{required[1]}+)"
    )
    return passed


def check_ngspice() -> bool:
    """Check if ngspice is installed."""
    try:
        result = subprocess.run(
            ['ngspice', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        passed = result.returncode == 0
        version = result.stdout.split('\n')[0] if passed else "not found"
        check("ngspice Installation", passed, version)
        return passed
    except (subprocess.TimeoutExpired, FileNotFoundError):
        check("ngspice Installation", False, "ngspice not found in PATH")
        return False


def check_python_packages() -> bool:
    """Check required Python packages."""
    required_packages = [
        'yaml',
        'numpy',
        'scipy',
        'anthropic',
        'openai',
    ]
    
    all_ok = True
    for package in required_packages:
        try:
            __import__(package)
            check(f"Python package: {package}", True)
        except ImportError:
            check(f"Python package: {package}", False, "Not installed")
            all_ok = False
    
    return all_ok


def check_directory_structure() -> bool:
    """Check that required directories exist."""
    base_dir = Path(__file__).parent.parent
    
    required_dirs = [
        "pdk/skywater130",
        "pdk/skywater130/gm_id_tables",
        "harness/design_verification",
        "data/dev/design/ota",
    ]
    
    all_ok = True
    for dir_path in required_dirs:
        full_path = base_dir / dir_path
        passed = full_path.exists() and full_path.is_dir()
        check(f"Directory: {dir_path}", passed)
        all_ok = all_ok and passed
    
    return all_ok


def check_pdk_files() -> bool:
    """Check PDK files and Gm/ID tables."""
    base_dir = Path(__file__).parent.parent
    pdk_dir = base_dir / "pdk" / "skywater130"
    
    # Check Gm/ID tables (placeholders are OK)
    gmid_dir = pdk_dir / "gm_id_tables"
    nfet_table = gmid_dir / "nfet_gmid_lut_placeholder.json"
    pfet_table = gmid_dir / "pfet_gmid_lut_placeholder.json"
    
    nfet_ok = nfet_table.exists()
    pfet_ok = pfet_table.exists()
    
    check("NMOS Gm/ID table", nfet_ok, str(nfet_table) if nfet_ok else "Missing")
    check("PMOS Gm/ID table", pfet_ok, str(pfet_table) if pfet_ok else "Missing")
    
    # Check for real PDK models (optional)
    models_dir = pdk_dir / "models"
    nfet_model = models_dir / "nfet_01v8.pm3.spice"
    pfet_model = models_dir / "pfet_01v8.pm3.spice"
    
    if nfet_model.exists() and pfet_model.exists():
        check("Real PDK Models", True, "Found (production-ready)")
    else:
        check("Real PDK Models", True, 
              f"{YELLOW}Optional: Using placeholder tables (OK for testing){RESET}")
    
    return nfet_ok and pfet_ok


def check_design_specs() -> bool:
    """Check that design specifications exist."""
    base_dir = Path(__file__).parent.parent
    design_dir = base_dir / "data" / "dev" / "design" / "ota"
    
    found_specs = 0
    for ota_dir in design_dir.glob("ota*"):
        spec_file = ota_dir / "verification" / "design_spec.json"
        if spec_file.exists():
            try:
                with open(spec_file, 'r') as f:
                    spec = json.load(f)
                if 'specifications' in spec:
                    found_specs += 1
            except:
                pass
    
    passed = found_specs > 0
    check("Design Specifications", passed, f"Found {found_specs} design test cases")
    return passed


def check_config() -> bool:
    """Check bench_config.yaml."""
    base_dir = Path(__file__).parent.parent
    config_file = base_dir / "bench_config.yaml"
    
    if not config_file.exists():
        check("bench_config.yaml", False, "File not found")
        return False
    
    # Check if design_verification section exists
    with open(config_file, 'r') as f:
        content = f.read()
        has_design_section = 'design_verification:' in content
    
    check("bench_config.yaml", True, 
          "Contains design_verification section" if has_design_section 
          else f"{YELLOW}Missing design_verification section{RESET}")
    
    return True


def check_api_keys() -> bool:
    """Check if API keys are configured."""
    import os
    
    openai_key = os.environ.get('OPENAI_API_KEY')
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
    
    if openai_key:
        check("OpenAI API Key", True, "Set")
    else:
        check("OpenAI API Key", True, f"{YELLOW}Not set (optional){RESET}")
    
    if anthropic_key:
        check("Anthropic API Key", True, "Set")
    else:
        check("Anthropic API Key", True, f"{YELLOW}Not set (optional){RESET}")
    
    return True  # API keys are optional for verification


def check_import_modules() -> bool:
    """Check if design verification modules can be imported."""
    base_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(base_dir))
    
    modules_ok = True
    
    try:
        from harness.design_verification import NetlistParser
        check("Import NetlistParser", True)
    except ImportError as e:
        check("Import NetlistParser", False, str(e))
        modules_ok = False
    
    try:
        from harness.design_verification import SpiceRunner
        check("Import SpiceRunner", True)
    except ImportError as e:
        check("Import SpiceRunner", False, str(e))
        modules_ok = False
    
    try:
        from harness.design_verification import DesignJudge
        check("Import DesignJudge", True)
    except ImportError as e:
        check("Import DesignJudge", False, str(e))
        modules_ok = False
    
    return modules_ok


def main():
    """Run all checks."""
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}Design Verification Setup Checker{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")
    
    checks = [
        ("Python Environment", [
            ("Python Version", check_python_version),
            ("Python Packages", check_python_packages),
        ]),
        ("External Dependencies", [
            ("ngspice", check_ngspice),
        ]),
        ("File Structure", [
            ("Directories", check_directory_structure),
            ("PDK Files", check_pdk_files),
            ("Design Specs", check_design_specs),
            ("Configuration", check_config),
        ]),
        ("Code Modules", [
            ("Imports", check_import_modules),
        ]),
        ("Optional", [
            ("API Keys", check_api_keys),
        ]),
    ]
    
    all_passed = True
    
    for section_name, section_checks in checks:
        print(f"\n{BLUE}{section_name}:{RESET}")
        section_passed = True
        for check_name, check_func in section_checks:
            try:
                result = check_func()
                section_passed = section_passed and result
            except Exception as e:
                check(check_name, False, f"Error: {str(e)}")
                section_passed = False
        
        if section_name != "Optional":
            all_passed = all_passed and section_passed
    
    # Summary
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    if all_passed:
        print(f"{GREEN}✓ All checks passed! Design verification is ready.{RESET}")
        print(f"\nNext steps:")
        print(f"  1. Set API keys (if not already set):")
        print(f"     export OPENAI_API_KEY='your-key'")
        print(f"  2. Run a test:")
        print(f"     python harness/run_design_eval.py --model openai:gpt-4o-mini --designs ota001")
        return 0
    else:
        print(f"{RED}✗ Some checks failed. Please fix the issues above.{RESET}")
        print(f"\nCommon fixes:")
        print(f"  - Install ngspice: brew install ngspice (macOS) or apt-get install ngspice (Linux)")
        print(f"  - Install Python packages: pip install -r requirements.txt")
        print(f"  - Check file structure and run from project root")
        return 1


if __name__ == '__main__':
    sys.exit(main())


#!/usr/bin/env python3
"""
Design Verification Evaluation Runner

Runs automated design verification using SPICE simulation for OTA circuits.
"""

import argparse
import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from harness.adapters import get_adapter
from harness.design_verification import NetlistParser, SpiceRunner, DesignJudge


class DesignEvaluator:
    """Main class for running design verification evaluations."""
    
    def __init__(self, config_path: Path, output_dir: Path, pdk_path: Path):
        """
        Initialize design evaluator.
        
        Args:
            config_path: Path to bench_config.yaml
            output_dir: Directory for saving results
            pdk_path: Path to PDK directory
        """
        self.config_path = config_path
        self.output_dir = output_dir
        self.pdk_path = pdk_path
        
        # Load config
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.parser = NetlistParser()
        self.spice_runner = SpiceRunner(pdk_path, output_dir / "simulations")
        
    def run_evaluation(self, model_name: str, test_cases: Optional[List[str]] = None):
        """
        Run design evaluation for specified model and test cases.
        
        Args:
            model_name: Name of LLM model to evaluate
            test_cases: List of design IDs to evaluate (None = all)
        """
        print(f"Starting design evaluation for {model_name}")
        print(f"PDK: {self.pdk_path}")
        print(f"Output: {self.output_dir}")
        print("-" * 60)
        
        # Get LLM adapter
        adapter = get_adapter(model_name)
        judge = DesignJudge(adapter)
        
        # Find design test cases
        design_cases = self._discover_design_cases()
        if test_cases:
            design_cases = [c for c in design_cases if c['design_id'] in test_cases]
        
        print(f"Found {len(design_cases)} design test cases")
        
        # Run each test case
        results = []
        for i, test_case in enumerate(design_cases, 1):
            print(f"\n[{i}/{len(design_cases)}] Evaluating {test_case['design_id']}...")
            result = self._evaluate_design(test_case, adapter, judge)
            results.append(result)
            
            # Save incremental results
            self._save_results(results, model_name)
        
        # Generate report
        self._generate_report(results, model_name)
        print(f"\nEvaluation complete! Results saved to {self.output_dir}")
    
    def _discover_design_cases(self) -> List[Dict]:
        """Discover all design test cases with verification specs."""
        data_dir = Path(self.config.get('data_root', 'data/dev'))
        design_dir = data_dir / "design" / "ota"
        
        cases = []
        for ota_dir in sorted(design_dir.glob("ota*")):
            verification_dir = ota_dir / "verification"
            spec_file = verification_dir / "design_spec.json"
            
            if spec_file.exists():
                with open(spec_file, 'r') as f:
                    spec = json.load(f)
                
                cases.append({
                    'design_id': ota_dir.name,
                    'spec_file': spec_file,
                    'spec': spec,
                    'testbench': verification_dir / "testbench_template.sp"
                })
        
        return cases
    
    def _evaluate_design(self, test_case: Dict, adapter, judge: DesignJudge) -> Dict:
        """Evaluate a single design test case."""
        design_id = test_case['design_id']
        spec = test_case['spec']
        
        result = {
            'design_id': design_id,
            'timestamp': datetime.now().isoformat(),
            'topology': spec.get('topology'),
            'status': 'pending'
        }
        
        try:
            # 1. Generate design using LLM
            print(f"  → Requesting design from LLM...")
            design_prompt = self._create_design_prompt(spec)
            llm_response = adapter.generate(design_prompt)
            result['llm_response'] = llm_response
            
            # 2. Extract netlist
            print(f"  → Parsing netlist...")
            netlist_raw = self.parser.extract_netlist(llm_response)
            if not netlist_raw:
                result['status'] = 'parse_failed'
                result['error'] = "Could not extract netlist from LLM response"
                return result
            
            parsed = self.parser.parse(netlist_raw)
            if not parsed.is_valid:
                result['status'] = 'invalid_netlist'
                result['error'] = f"Invalid netlist: {parsed.errors}"
                return result
            
            result['netlist'] = parsed.cleaned_netlist
            
            # 3. Run SPICE simulation
            print(f"  → Running SPICE simulation...")
            sim_results = self.spice_runner.run_simulation(
                parsed.cleaned_netlist,
                spec,
                design_id
            )
            
            if not sim_results.success:
                result['status'] = 'simulation_failed'
                result['error'] = sim_results.errors
                return result
            
            result['simulation'] = sim_results.to_dict()
            
            # 4. Judge results
            print(f"  → Evaluating against specifications...")
            judgment = judge.evaluate(
                sim_results.metrics,
                spec,
                parsed.cleaned_netlist
            )
            
            result['judgment'] = judgment.to_dict()
            result['status'] = 'pass' if judgment.overall_pass else 'fail'
            result['score'] = judgment.score
            
            print(f"  ✓ Score: {judgment.score:.1f}/100 - {'PASS' if judgment.overall_pass else 'FAIL'}")
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            print(f"  ✗ Error: {e}")
        
        return result
    
    def _create_design_prompt(self, spec: Dict) -> str:
        """Create design prompt for LLM with specifications and Gm/ID tables."""
        
        # Load Gm/ID tables summary
        gmid_summary = self._load_gmid_summary()
        
        prompt = f"""You are an expert analog IC designer. Design a {spec.get('topology')} operational transconductance amplifier (OTA) that meets the following specifications:

TECHNOLOGY: SkyWater 130nm PDK
SUPPLY VOLTAGE: {spec['pdk']['supply_voltage']}V

SPECIFICATIONS:
"""
        
        for spec_name, spec_def in spec['specifications'].items():
            min_val = spec_def.get('min', '')
            max_val = spec_def.get('max', '')
            target = spec_def.get('target', '')
            unit = spec_def.get('unit', '')
            
            if min_val and max_val:
                prompt += f"- {spec_name}: {min_val} to {max_val} {unit}\n"
            elif min_val:
                prompt += f"- {spec_name}: min {min_val} {unit}\n"
            elif max_val:
                prompt += f"- {spec_name}: max {max_val} {unit}\n"
            if target:
                prompt += f"  (target: {target} {unit})\n"
        
        prompt += f"""
TEST CONDITIONS:
- Load capacitance: {spec['test_conditions']['load_capacitance']}
- Input common-mode: {spec['test_conditions']['input_common_mode']}V

GM/ID TABLES REFERENCE:
{gmid_summary}

REQUIREMENTS:
1. Provide a complete SPICE netlist for the OTA
2. Use realistic device sizes (W and L values)
3. Include all necessary bias voltages and currents
4. Add brief comments explaining your design choices
5. Ensure the design can be simulated with ngspice

FORMAT YOUR RESPONSE:
```spice
* Your SPICE netlist here
* with comments
[netlist content]
.end
```

Then explain your design methodology and expected performance.
"""
        return prompt
    
    def _load_gmid_summary(self) -> str:
        """Load and summarize Gm/ID tables for inclusion in prompt."""
        gmid_dir = self.pdk_path / "gm_id_tables"
        
        summary = """
Available Gm/ID operating points (approximate):
- High Gm/ID (20-25 S/A): Weak inversion, low power, slow
- Medium Gm/ID (10-15 S/A): Moderate inversion, balanced
- Low Gm/ID (5-8 S/A): Strong inversion, high speed, high power

Typical values for sky130:
- NMOS: Vth ≈ 0.42V
- PMOS: Vth ≈ -0.45V
- Minimum L: 150nm
- Typical L for analog: 500nm to 1um
"""
        return summary
    
    def _save_results(self, results: List[Dict], model_name: str):
        """Save results to JSON file."""
        output_file = self.output_dir / f"{model_name}_design_results.json"
        with open(output_file, 'w') as f:
            json.dump({
                'model': model_name,
                'timestamp': datetime.now().isoformat(),
                'pdk': str(self.pdk_path),
                'results': results
            }, f, indent=2)
    
    def _generate_report(self, results: List[Dict], model_name: str):
        """Generate human-readable report."""
        report_file = self.output_dir / f"{model_name}_design_report.txt"
        
        with open(report_file, 'w') as f:
            f.write(f"Design Verification Report\n")
            f.write(f"{'=' * 60}\n")
            f.write(f"Model: {model_name}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Total test cases: {len(results)}\n\n")
            
            # Summary statistics
            passed = sum(1 for r in results if r.get('status') == 'pass')
            failed = sum(1 for r in results if r.get('status') == 'fail')
            errors = sum(1 for r in results if r.get('status') not in ['pass', 'fail'])
            avg_score = sum(r.get('score', 0) for r in results) / len(results) if results else 0
            
            f.write(f"Summary:\n")
            f.write(f"  Passed: {passed}/{len(results)}\n")
            f.write(f"  Failed: {failed}/{len(results)}\n")
            f.write(f"  Errors: {errors}/{len(results)}\n")
            f.write(f"  Average Score: {avg_score:.1f}/100\n\n")
            
            # Detailed results
            f.write(f"Detailed Results:\n")
            f.write(f"{'-' * 60}\n\n")
            
            for result in results:
                f.write(f"Design: {result['design_id']}\n")
                f.write(f"Status: {result['status']}\n")
                if 'score' in result:
                    f.write(f"Score: {result['score']:.1f}/100\n")
                if 'judgment' in result:
                    f.write(f"Specifications:\n")
                    for spec_name, spec_result in result['judgment']['spec_results'].items():
                        status = "✓" if spec_result['pass'] else "✗"
                        f.write(f"  {status} {spec_name}: {spec_result['message']}\n")
                if 'error' in result:
                    f.write(f"Error: {result['error']}\n")
                f.write(f"\n")
        
        print(f"\nReport saved to {report_file}")


def main():
    parser = argparse.ArgumentParser(description='Run design verification evaluation')
    parser.add_argument('--model', required=True, help='Model name (e.g., gpt-4, claude-3.5)')
    parser.add_argument('--config', type=Path, default=Path('bench_config.yaml'),
                       help='Path to bench config file')
    parser.add_argument('--output', type=Path, default=None,
                       help='Output directory (default: outputs/design_run_TIMESTAMP)')
    parser.add_argument('--pdk-path', type=Path, 
                       default=Path(__file__).parent.parent / 'pdk' / 'skywater130',
                       help='Path to PDK directory')
    parser.add_argument('--designs', nargs='+', default=None,
                       help='Specific design IDs to evaluate (default: all)')
    
    args = parser.parse_args()
    
    # Create output directory
    if args.output is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        args.output = Path('outputs') / f'design_run_{timestamp}'
    
    # Create evaluator
    evaluator = DesignEvaluator(
        config_path=args.config,
        output_dir=args.output,
        pdk_path=args.pdk_path
    )
    
    # Run evaluation
    evaluator.run_evaluation(args.model, args.designs)


if __name__ == '__main__':
    main()


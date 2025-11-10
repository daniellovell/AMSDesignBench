"""
SPICE Runner

Executes ngspice simulations and extracts performance metrics.
"""

import subprocess
import tempfile
import re
import os
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass, field
import json


@dataclass
class SimulationResults:
    """Container for simulation results and metrics."""
    success: bool
    metrics: Dict[str, float] = field(default_factory=dict)
    raw_output: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'success': self.success,
            'metrics': self.metrics,
            'errors': self.errors,
            'warnings': self.warnings
        }


class SpiceRunner:
    """Runs ngspice simulations and extracts results."""
    
    def __init__(self, pdk_path: Path, work_dir: Optional[Path] = None):
        """
        Initialize SPICE runner.
        
        Args:
            pdk_path: Path to PDK directory
            work_dir: Working directory for simulation files (temp if None)
        """
        self.pdk_path = Path(pdk_path)
        self.work_dir = Path(work_dir) if work_dir else Path(tempfile.mkdtemp())
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if ngspice is available
        try:
            result = subprocess.run(
                ['ngspice', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                raise RuntimeError("ngspice not properly installed")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise RuntimeError(f"ngspice not found or not working: {e}")
    
    def run_simulation(self, netlist: str, design_spec: Dict, 
                      design_id: str = "ota") -> SimulationResults:
        """
        Run simulation and extract metrics.
        
        Args:
            netlist: Complete SPICE netlist
            design_spec: Design specification dictionary
            design_id: Identifier for this design
            
        Returns:
            SimulationResults object
        """
        # Create simulation directory
        sim_dir = self.work_dir / design_id
        sim_dir.mkdir(parents=True, exist_ok=True)
        
        # Load testbench template
        testbench = self._create_testbench(netlist, design_spec, sim_dir, design_id)
        
        # Write testbench to file
        netlist_file = sim_dir / f"{design_id}_tb.sp"
        with open(netlist_file, 'w') as f:
            f.write(testbench)
        
        # Run ngspice from PDK root directory so relative includes in corner files work
        try:
            result = subprocess.run(
                ['ngspice', '-b', str(netlist_file.absolute())],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(self.pdk_path)  # Run from PDK root, not models/
            )
            
            if result.returncode != 0:
                return SimulationResults(
                    success=False,
                    raw_output=result.stdout + result.stderr,
                    errors=[f"Simulation failed with return code {result.returncode}",
                           result.stderr]
                )
            
            # Parse results from stdout and results file
            metrics = self._parse_results(result.stdout, sim_dir)
            
            # Also parse results.txt if it exists
            results_file = sim_dir / "results.txt"
            if results_file.exists():
                results_content = results_file.read_text()
                file_metrics = self._parse_results(results_content, sim_dir)
                metrics.update(file_metrics)
            
            # Add measurement frequencies to metrics if available (for filters)
            if hasattr(self, '_last_measurement_freqs'):
                metrics['_measurement_frequencies'] = self._last_measurement_freqs
            
            warnings = self._extract_warnings(result.stdout)
            
            return SimulationResults(
                success=True,
                metrics=metrics,
                raw_output=result.stdout,
                warnings=warnings
            )
            
        except subprocess.TimeoutExpired:
            return SimulationResults(
                success=False,
                errors=["Simulation timed out after 60 seconds"]
            )
        except Exception as e:
            return SimulationResults(
                success=False,
                errors=[f"Simulation error: {str(e)}"]
            )
    
    def _create_testbench(self, dut_netlist: str, design_spec: Dict, 
                         sim_dir: Path, design_id: str = None) -> str:
        """Create complete testbench from template and DUT netlist."""
        
        # Load template based on topology and design_id
        topology = design_spec.get('topology', 'generic')
        if not design_id:
            design_id = design_spec.get('design_id')
        template_path = self._find_template(topology, design_id)
        
        with open(template_path, 'r') as f:
            template = f.read()
        
        # Extract parameters from design spec
        specs = design_spec.get('specifications', {})
        vdd = specs.get('supply_voltage', {}).get('value', 1.8)
        cl = specs.get('load_capacitance', {}).get('value', 5e-12)
        temp = design_spec.get('pdk', {}).get('temperature', 27)
        
        # Use test conditions if available
        test_cond = design_spec.get('test_conditions', {})
        vcm = test_cond.get('input_common_mode', 0.9)
        if isinstance(test_cond.get('load_capacitance'), str):
            # Parse strings like "5p" to float
            cl_str = test_cond['load_capacitance']
            if cl_str.endswith('p'):
                cl = float(cl_str[:-1]) * 1e-12
            elif cl_str.endswith('f'):
                cl = float(cl_str[:-1]) * 1e-15
        
        # Calculate dynamic measurement frequencies for filters
        passband_freq = 10  # Default for non-filter circuits
        stopband_freq = 100000  # Default for non-filter circuits
        
        filter_type = design_spec.get('filter_type')
        if filter_type:
            # Find characteristic frequency
            char_freq = None
            for spec_name, spec_data in specs.items():
                if 'cutoff_frequency' in spec_name:
                    char_freq = spec_data.get('target') or spec_data.get('value')
                    break
                elif 'center_frequency' in spec_name:
                    char_freq = spec_data.get('target') or spec_data.get('value')
                    break
                elif 'notch_frequency' in spec_name:
                    char_freq = spec_data.get('target') or spec_data.get('value')
                    break
                elif 'characteristic_frequency' in spec_name:
                    char_freq = spec_data.get('target') or spec_data.get('value')
                    break
            
            if char_freq:
                # Calculate measurement frequencies based on filter type
                if filter_type in ['low_pass', 'band_stop']:
                    # Passband at fc/10, stopband at fc*10
                    passband_freq = max(10, char_freq / 10)
                    stopband_freq = min(1e6, char_freq * 10)
                elif filter_type == 'high_pass':
                    # Stopband at fc/10, passband at fc*10
                    stopband_freq = max(10, char_freq / 10)
                    passband_freq = min(1e6, char_freq * 10)
                elif filter_type in ['band_pass', 'all_pass']:
                    # For band-pass: passband at fc, stopband at fc/10
                    passband_freq = char_freq
                    stopband_freq = max(10, char_freq / 10)
                else:
                    # Default: use fc/10 and fc*10
                    passband_freq = max(10, char_freq / 10)
                    stopband_freq = min(1e6, char_freq * 10)
        
        # Substitutions
        pdk_models = self.pdk_path / "models"
        output_file = sim_dir / "results.txt"
        plot_file = sim_dir / "plots"
        
        testbench = template.format(
            pdk_models_path=pdk_models,
            dut_netlist=dut_netlist,
            output_file=output_file,
            plot_file=plot_file,
            VDD=vdd,
            CL=cl,
            VCM=vcm,
            TEMP=temp,
            passband_freq=passband_freq,
            stopband_freq=stopband_freq
        )
        
        # Store measurement frequencies in a temporary attribute for later retrieval
        self._last_measurement_freqs = {
            'passband_freq': passband_freq,
            'stopband_freq': stopband_freq
        }
        
        return testbench
    
    def _find_template(self, topology: str, design_id: str = None) -> Path:
        """Find appropriate testbench template for topology."""
        # Map topology to template
        design_base = Path(__file__).parent.parent.parent / "data" / "dev" / "design"
        
        # First, try to match by design_id if provided (most specific)
        if design_id:
            # Try filters first
            for family in ['filters', 'ota', 'feedback']:
                specific_template = design_base / family / design_id / "verification" / "testbench_template.sp"
                if specific_template.exists():
                    return specific_template
        
        # Try to find matching topology in all design families
        for family in ['filters', 'ota', 'feedback']:
            family_dir = design_base / family
            if not family_dir.exists():
                continue
            
            for item_dir in sorted(family_dir.glob("*")):
                if not item_dir.is_dir():
                    continue
                verification_dir = item_dir / "verification"
                if verification_dir.exists():
                    template = verification_dir / "testbench_template.sp"
                    if template.exists():
                        # Read design_spec to check if topology matches
                        spec_file = verification_dir / "design_spec.json"
                        if spec_file.exists():
                            import json
                            with open(spec_file, 'r') as f:
                                spec = json.load(f)
                            if spec.get('topology') == topology:
                                return template
        
        # Fallback: return first found template
        for family in ['filters', 'ota', 'feedback']:
            family_dir = design_base / family
            if not family_dir.exists():
                continue
            for item_dir in sorted(family_dir.glob("*")):
                template = item_dir / "verification" / "testbench_template.sp"
                if template.exists():
                    return template
        
        raise FileNotFoundError("No testbench template found")
    
    def _parse_results(self, output: str, sim_dir: Path) -> Dict[str, float]:
        """Extract performance metrics from simulation output."""
        metrics = {}
        
        # Parse ngspice measurement output format
        # Format: "  measurement_name  =  1.234e+56 at ..."
        # Also handles: " meas ac measurement_name find ..."
        meas_result_pattern = r'^\s*(\w+)\s+=\s+([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)'
        
        for line in output.split('\n'):
            # Extract measurement results
            match = re.search(meas_result_pattern, line)
            if match:
                key, value = match.groups()
                try:
                    metrics[key.lower()] = float(value)
                except ValueError:
                    pass
        
        # Also look for variable assignments in output
        # Pattern: "let variable = value" or computed results
        let_pattern = r'let\s+(\w+)\s*=\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)'
        for match in re.finditer(let_pattern, output):
            key, value = match.groups()
            try:
                metrics[key.lower()] = float(value)
            except ValueError:
                pass
        
        return metrics
    
    def _extract_warnings(self, output: str) -> List[str]:
        """Extract warnings from simulation output."""
        warnings = []
        for line in output.split('\n'):
            if 'warning' in line.lower():
                warnings.append(line.strip())
        return warnings
    
    def cleanup(self):
        """Clean up temporary simulation files."""
        import shutil
        if self.work_dir.exists() and 'tmp' in str(self.work_dir):
            shutil.rmtree(self.work_dir)


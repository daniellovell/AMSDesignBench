"""
SPICE Runner

Executes ngspice simulations and extracts performance metrics.
"""

import subprocess
import tempfile
import re
import os
from pathlib import Path
from typing import Dict, Optional, List, Any, Tuple
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
        # Fast path: structure-only verification (no ngspice)
        # Used by feedback design tasks where we want objective, deterministic scoring
        # based on topology/connectivity rather than analog performance.
        verification_mode = str(design_spec.get("verification_mode") or "").strip().lower()
        if verification_mode in {"structure", "netlist_structure", "structure_only"}:
            try:
                metrics = self._verify_netlist_structure(netlist, design_spec)
                return SimulationResults(success=True, metrics=metrics, raw_output="")
            except Exception as e:
                return SimulationResults(success=False, metrics={}, errors=[f"Structure verification error: {e}"])

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
            
            # Parse results from stdout+stderr and results file.
            # ngspice can emit some `print` output on stderr depending on build/config.
            raw_output = (result.stdout or "") + "\n" + (result.stderr or "")
            metrics = self._parse_results(raw_output, sim_dir)
            
            # Also parse results.txt if it exists
            results_file = sim_dir / "results.txt"
            if results_file.exists():
                results_content = results_file.read_text()
                file_metrics = self._parse_results(results_content, sim_dir)
                metrics.update(file_metrics)
            
            # Add measurement frequencies to metrics if available (for filters)
            if hasattr(self, '_last_measurement_freqs'):
                metrics['_measurement_frequencies'] = self._last_measurement_freqs
            
            warnings = self._extract_warnings(raw_output)
            
            return SimulationResults(
                success=True,
                metrics=metrics,
                raw_output=raw_output,
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

    def _strip_code_fences(self, text: str) -> str:
        """Remove markdown code fences if present."""
        s = text.strip()
        if s.startswith("```"):
            # Remove first fence line and trailing fence if present
            lines = s.splitlines()
            # drop first line
            lines = lines[1:]
            # drop trailing fence
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return s

    def _parse_spice_lines(self, netlist: str) -> List[str]:
        """Return normalized SPICE lines (comments removed, continuations joined)."""
        s = self._strip_code_fences(netlist)
        raw_lines = s.splitlines()
        out: List[str] = []
        buf = ""
        for raw in raw_lines:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(("*", ";", "//")):
                continue
            # remove trailing inline comments starting with ';' or '//'
            cpos = len(line)
            p2 = line.find("//")
            if p2 != -1:
                cpos = min(cpos, p2)
            p3 = line.find(";")
            if p3 != -1:
                cpos = min(cpos, p3)
            line = line[:cpos].strip()
            if not line:
                continue
            # continuation line
            if line.startswith("+"):
                buf += " " + line[1:].strip()
                continue
            if buf:
                out.append(buf)
            buf = line
        if buf:
            out.append(buf)
        return out

    def _find_opamp_instance(self, lines: List[str]) -> Optional[Tuple[str, str, str, str]]:
        """
        Find an opamp instance line of the form:
          XU? in_n in_p out opamp [params...]
        Returns (inst_name, in_n, in_p, out) or None.
        """
        for ln in lines:
            if not ln or ln[0].upper() != "X":
                continue
            parts = ln.split()
            if len(parts) < 5:
                continue
            # Find the token 'opamp' (subckt name) and assume 3 pins immediately before it
            try:
                idx = [p.lower() for p in parts].index("opamp")
            except ValueError:
                continue
            if idx < 4:
                continue
            inst = parts[0]
            in_n, in_p, out = parts[idx - 3], parts[idx - 2], parts[idx - 1]
            return inst, in_n, in_p, out
        return None

    def _has_component_between(self, lines: List[str], prefix: str, a: str, b: str) -> bool:
        """Check for a 2-terminal component (R/C) between nodes a and b (order-insensitive)."""
        pa = a.lower()
        pb = b.lower()
        for ln in lines:
            if not ln or ln[0].upper() != prefix.upper():
                continue
            parts = ln.split()
            if len(parts) < 4:
                continue
            n1 = parts[1].lower()
            n2 = parts[2].lower()
            if (n1 == pa and n2 == pb) or (n1 == pb and n2 == pa):
                return True
        return False

    def _verify_netlist_structure(self, netlist: str, design_spec: Dict[str, Any]) -> Dict[str, float]:
        """
        Deterministic structure checks for feedback amplifier design tasks.
        Returns metrics as floats (0.0/1.0) so the existing objective scoring can apply.
        """
        topology = str(design_spec.get("topology") or "").strip().lower()
        lines = self._parse_spice_lines(netlist)

        op = self._find_opamp_instance(lines)
        has_opamp = 1.0 if op else 0.0
        metrics: Dict[str, float] = {"has_opamp": has_opamp}
        if not op:
            # If no opamp, all topology checks fail
            metrics.update(
                {
                    "noninv_grounded": 0.0,
                    "has_feedback_resistor": 0.0,
                    "has_feedback_capacitor": 0.0,
                    "has_input_resistor": 0.0,
                    "has_resistive_divider": 0.0,
                }
            )
            return metrics

        _, in_n, in_p, out = op
        metrics["noninv_grounded"] = 1.0 if in_p.strip().lower() in {"0", "gnd"} else 0.0

        if topology == "tia_feedback_resistor":
            metrics["has_feedback_resistor"] = 1.0 if self._has_component_between(lines, "R", out, in_n) else 0.0
            metrics["has_feedback_capacitor"] = 0.0
            metrics["has_input_resistor"] = 0.0
            metrics["has_resistive_divider"] = 0.0
        elif topology == "tia_feedback_capacitor":
            metrics["has_feedback_capacitor"] = 1.0 if self._has_component_between(lines, "C", out, in_n) else 0.0
            metrics["has_feedback_resistor"] = 0.0
            metrics["has_input_resistor"] = 0.0
            metrics["has_resistive_divider"] = 0.0
        elif topology == "noninverting_voltage_amp":
            # Need two resistors: out<->in_n and in_n<->0
            has_r_out = self._has_component_between(lines, "R", out, in_n)
            has_r_gnd = self._has_component_between(lines, "R", in_n, "0") or self._has_component_between(lines, "R", in_n, "gnd")
            metrics["has_resistive_divider"] = 1.0 if (has_r_out and has_r_gnd) else 0.0
            metrics["has_feedback_resistor"] = 1.0 if has_r_out else 0.0
            metrics["has_input_resistor"] = 0.0
            metrics["has_feedback_capacitor"] = 0.0
        elif topology == "inverting_voltage_amp":
            # Need feedback resistor out<->in_n and input resistor in_n<->S_in (or any non-ground node)
            has_rf = self._has_component_between(lines, "R", out, in_n)
            # Find any resistor from in_n to a non-ground, non-out node (treat as input resistor)
            has_rin = False
            in_n_l = in_n.lower()
            out_l = out.lower()
            for ln in lines:
                if not ln or ln[0].upper() != "R":
                    continue
                parts = ln.split()
                if len(parts) < 4:
                    continue
                n1 = parts[1].lower()
                n2 = parts[2].lower()
                if in_n_l not in {n1, n2}:
                    continue
                other = n2 if n1 == in_n_l else n1
                if other in {"0", "gnd", out_l, in_n_l}:
                    continue
                has_rin = True
                break
            metrics["has_feedback_resistor"] = 1.0 if has_rf else 0.0
            metrics["has_input_resistor"] = 1.0 if has_rin else 0.0
            metrics["has_feedback_capacitor"] = 0.0
            metrics["has_resistive_divider"] = 0.0
        else:
            # Unknown topology; expose basics only
            metrics.setdefault("has_feedback_resistor", 0.0)
            metrics.setdefault("has_feedback_capacitor", 0.0)
            metrics.setdefault("has_input_resistor", 0.0)
            metrics.setdefault("has_resistive_divider", 0.0)

        # One consolidated structural metric (useful for simple specs)
        if topology.startswith("tia_feedback_"):
            metrics["structural_correctness"] = 1.0 if (metrics["has_opamp"] and metrics["noninv_grounded"] and (metrics["has_feedback_resistor"] or metrics["has_feedback_capacitor"])) else 0.0
        elif topology == "noninverting_voltage_amp":
            metrics["structural_correctness"] = 1.0 if (metrics["has_opamp"] and metrics["has_resistive_divider"] and metrics["noninv_grounded"] == 0.0) else 0.0
        elif topology == "inverting_voltage_amp":
            metrics["structural_correctness"] = 1.0 if (metrics["has_opamp"] and metrics["noninv_grounded"] and metrics["has_feedback_resistor"] and metrics["has_input_resistor"]) else 0.0
        else:
            metrics["structural_correctness"] = 0.0

        return metrics
    
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

        # Optional preprocessing of DUT netlist (e.g., strip placeholder subckts that
        # the verification testbench provides in a functional form).
        preprocess = design_spec.get("preprocess") if isinstance(design_spec.get("preprocess"), dict) else {}
        strip_subckts = preprocess.get("strip_subckts") if isinstance(preprocess.get("strip_subckts"), list) else []
        if strip_subckts:
            dut_netlist = self._strip_subckt_blocks(dut_netlist, [str(x) for x in strip_subckts])
        
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

    def _strip_subckt_blocks(self, dut_netlist: str, subckt_names: List[str]) -> str:
        """
        Remove `.subckt <name> ... .ends` blocks for each name in subckt_names (case-insensitive).
        This is used for feedback verification where the testbench provides a functional `opamp` model.
        """
        names = {n.strip().lower() for n in subckt_names if str(n).strip()}
        if not names:
            return dut_netlist
        lines = self._strip_code_fences(dut_netlist).splitlines()
        out: List[str] = []
        skipping = False
        current = ""
        for raw in lines:
            s = raw.strip()
            low = s.lower()
            if not skipping and low.startswith(".subckt"):
                parts = low.split()
                if len(parts) >= 2 and parts[1] in names:
                    skipping = True
                    current = parts[1]
                    continue
            if skipping:
                if low.startswith(".ends"):
                    # End of any subckt; stop skipping
                    skipping = False
                    current = ""
                continue
            out.append(raw)
        return "\n".join(out).strip() + "\n"
    
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
        
        # Parse ngspice print output format
        # Format: "power = 1.234e-03" from print statements
        print_pattern = r'^\s*(\w+)\s*=\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*$'
        for line in output.split('\n'):
            match = re.search(print_pattern, line)
            if match:
                key, value = match.groups()
                try:
                    # Skip common variable names that aren't metrics
                    if key.lower() not in ['i', 'j', 'k', 'n', 'x', 'y', 'z']:
                        val = float(value)
                        # Filter out sentinel values (e.g., quality_factor = -1 means invalid)
                        if val < 0 and key.lower() in ['quality_factor', 'bandpass_bandwidth']:
                            continue  # Don't include invalid measurements
                        metrics[key.lower()] = val
                except ValueError:
                    pass
        
        # Filter out invalid sentinel values (negative for metrics that should be positive)
        filtered_metrics = {}
        for key, value in metrics.items():
            if value < 0 and key in ['quality_factor', 'bandpass_bandwidth', 'center_frequency', 
                                      'fc_low', 'fc_high', 'peak_freq']:
                # Skip invalid measurements (sentinel value -1 or negative frequencies)
                continue
            filtered_metrics[key] = value
        
        return filtered_metrics
    
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


"""
Netlist Parser

Extracts SPICE netlists from LLM responses, validates syntax,
and prepares them for simulation.
"""

import re
from typing import Optional, Dict, List
from dataclasses import dataclass


@dataclass
class ParsedNetlist:
    """Container for parsed netlist information."""
    raw_netlist: str
    cleaned_netlist: str
    devices: List[str]
    nodes: List[str]
    subcircuits: List[str]
    is_valid: bool
    errors: List[str]


class NetlistParser:
    """Parser for extracting and validating SPICE netlists from text."""
    
    # Common SPICE statement patterns
    SPICE_START_PATTERNS = [
        r'^\*\s*SPICE',
        r'^\*\s*Netlist',
        r'^\.title',
        r'^\.subckt',
        r'^\.param',  # Parameter definitions (must come before devices!)
        r'^[MRCLIVX]\w*\s+',  # Device lines
    ]
    
    SPICE_END_PATTERNS = [
        r'^\.end\s*$',
        r'^\.ends\s*$',
    ]
    
    def __init__(self):
        self.spice_start_re = re.compile('|'.join(self.SPICE_START_PATTERNS), re.IGNORECASE | re.MULTILINE)
        self.spice_end_re = re.compile('|'.join(self.SPICE_END_PATTERNS), re.IGNORECASE | re.MULTILINE)
    
    def extract_netlist(self, llm_response: str) -> Optional[str]:
        """
        Extract SPICE netlist from LLM response text.
        
        Looks for code blocks or SPICE-formatted sections.
        
        Args:
            llm_response: Raw text response from LLM
            
        Returns:
            Extracted netlist string, or None if not found
        """
        # Try to find code blocks first (markdown style)
        code_block_pattern = r'```(?:spice|netlist)?\s*\n(.*?)\n```'
        code_blocks = re.findall(code_block_pattern, llm_response, re.DOTALL | re.IGNORECASE)
        
        for block in code_blocks:
            if self._looks_like_spice(block):
                return block.strip()
        
        # Look for SPICE sections without code blocks
        lines = llm_response.split('\n')
        netlist_lines = []
        in_netlist = False
        
        for line in lines:
            # Check for start of SPICE section
            if not in_netlist and self.spice_start_re.search(line):
                in_netlist = True
                netlist_lines.append(line)
                continue
            
            # Check for end of SPICE section
            if in_netlist and self.spice_end_re.search(line):
                netlist_lines.append(line)
                break
            
            # Collect lines while in netlist
            if in_netlist:
                netlist_lines.append(line)
        
        if netlist_lines:
            return '\n'.join(netlist_lines).strip()
        
        return None
    
    def _looks_like_spice(self, text: str) -> bool:
        """Check if text looks like a SPICE netlist."""
        # Check for common SPICE elements
        has_devices = bool(re.search(r'^[MRCLIVX]\w+\s+', text, re.MULTILINE | re.IGNORECASE))
        has_directives = bool(re.search(r'^\.(title|subckt|end|param)', text, re.MULTILINE | re.IGNORECASE))
        return has_devices or has_directives
    
    def parse(self, netlist: str) -> ParsedNetlist:
        """
        Parse and validate a SPICE netlist.
        
        Args:
            netlist: SPICE netlist string
            
        Returns:
            ParsedNetlist object with parsed information
        """
        errors = []
        devices = []
        nodes = set()
        subcircuits = []
        
        # Clean the netlist
        cleaned = self._clean_netlist(netlist)
        lines = cleaned.split('\n')
        
        # Parse each line
        for i, line in enumerate(lines, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('*'):
                continue
            
            # Skip directives
            if line.startswith('.'):
                if line.startswith('.subckt'):
                    subcircuits.append(line)
                continue
            
            # Parse device line
            try:
                parts = line.split()
                if not parts:
                    continue
                
                device_name = parts[0]
                devices.append(device_name)
                
                # Extract node names (varies by device type)
                device_type = device_name[0].upper()
                if device_type == 'M':  # MOSFET: D G S B
                    if len(parts) >= 5:
                        nodes.update(parts[1:5])
                elif device_type in ['R', 'C', 'L']:  # Two-terminal
                    if len(parts) >= 3:
                        nodes.update(parts[1:3])
                elif device_type == 'V':  # Voltage source
                    if len(parts) >= 3:
                        nodes.update(parts[1:3])
                elif device_type == 'X':  # Subcircuit instance
                    # Nodes depend on subcircuit definition
                    if len(parts) >= 3:
                        # Last part is subcircuit name, rest are nodes
                        nodes.update(parts[1:-1])
                        
            except Exception as e:
                errors.append(f"Line {i}: Parse error - {str(e)}")
        
        # Validation checks
        is_valid = self._validate_netlist(devices, list(nodes), subcircuits, errors)
        
        return ParsedNetlist(
            raw_netlist=netlist,
            cleaned_netlist=cleaned,
            devices=devices,
            nodes=list(nodes),
            subcircuits=subcircuits,
            is_valid=is_valid,
            errors=errors
        )
    
    def _clean_netlist(self, netlist: str) -> str:
        """Clean and normalize netlist formatting for testbench integration."""
        lines = []
        in_control_block = False
        
        for line in netlist.split('\n'):
            stripped = line.strip()
            
            # Skip .control blocks (testbench will provide its own)
            if stripped.startswith('.control'):
                in_control_block = True
                continue
            if stripped.startswith('.endc'):
                in_control_block = False
                continue
            if in_control_block:
                continue
            
            # Skip .end statements (testbench will provide)
            if stripped.startswith('.end'):
                continue
            
            # Skip .lib directives (testbench includes models properly)
            if stripped.startswith('.lib'):
                continue
            
            # Skip .option directives (testbench sets options)
            if stripped.startswith('.option'):
                continue
            
            # Skip .title directives (testbench has title)
            if stripped.startswith('.title'):
                continue
            
            # Skip power supply definitions (testbench provides these)
            if re.match(r'^V(dd|ss|cc|ee)\s+', stripped, re.IGNORECASE):
                continue
            
            # Skip load capacitor definitions (testbench provides these)
            if re.match(r'^C(L|load)\s+', stripped, re.IGNORECASE):
                continue
            
            # Fix .param lines with unit suffixes (remove 'u' from L/W values when scale=1.0u is set)
            if stripped.startswith('.param'):
                # Replace patterns like "L1=0.5u", "W1=10u", "Lp=0.5u", "Ltail=1u" with values without 'u'
                # This is necessary when .option scale=1.0u is set in the testbench
                line = re.sub(r'([LW](?:\d+|p|tail))=(\d+(?:\.\d+)?)u\b', r'\1=\2', line)
            
            # Handle line continuations
            if line.startswith('+'):
                if lines:
                    lines[-1] += ' ' + line[1:].strip()
                continue
            lines.append(line)
        
        return '\n'.join(lines)
    
    def _validate_netlist(self, devices: List[str], nodes: List[str], 
                         subcircuits: List[str], errors: List[str]) -> bool:
        """Validate netlist structure and content."""
        
        # Must have at least some devices
        if not devices:
            errors.append("No devices found in netlist")
            return False
        
        # Should have ground node (0 or GND)
        has_ground = '0' in nodes or 'GND' in [n.upper() for n in nodes]
        if not has_ground:
            errors.append("Warning: No ground node (0 or GND) found")
        
        # Check for required device types (at least one transistor)
        device_types = set(d[0].upper() for d in devices)
        if 'M' not in device_types and 'X' not in device_types:
            errors.append("Warning: No transistors (M) or subcircuits (X) found")
        
        return len([e for e in errors if not e.startswith("Warning")]) == 0
    
    def prepare_for_simulation(self, parsed: ParsedNetlist, 
                              pdk_path: str, 
                              supply_voltage: float = 1.8) -> str:
        """
        Prepare netlist for simulation by adding necessary headers and supplies.
        
        Args:
            parsed: ParsedNetlist object
            pdk_path: Path to PDK models
            supply_voltage: Supply voltage in volts
            
        Returns:
            Complete SPICE netlist ready for simulation
        """
        lines = [
            f"* Auto-generated testbench from AI design",
            f"",
            f".title AI-Generated OTA Design Verification",
            f"",
            f"* Include PDK models",
            f".include {pdk_path}/models/nfet_01v8.pm3.spice",
            f".include {pdk_path}/models/pfet_01v8.pm3.spice",
            f"",
            f"* Supply",
            f"VDD vdd 0 DC {supply_voltage}",
            f"",
            f"* AI-Generated Design",
        ]
        
        lines.extend(parsed.cleaned_netlist.split('\n'))
        
        lines.append("")
        lines.append(".end")
        
        return '\n'.join(lines)


def parse_netlist_from_markdown(markdown_text: str) -> Optional[str]:
    """
    Helper function to extract and clean SPICE netlist from markdown/LLM response.
    
    Args:
        markdown_text: Text containing SPICE netlist (possibly in markdown code blocks)
        
    Returns:
        Cleaned netlist string, or None if not found
    """
    parser = NetlistParser()
    netlist = parser.extract_netlist(markdown_text)
    if netlist:
        # Clean the netlist (strip .control blocks, .end statements, etc.)
        return parser._clean_netlist(netlist)
    return None

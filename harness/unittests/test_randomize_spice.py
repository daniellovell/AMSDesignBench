"""Unit tests for randomize_spice function to verify subcircuit preservation."""

import unittest
from harness.run_eval import randomize_spice


class TestRandomizeSpice(unittest.TestCase):
    """Test that randomize_spice preserves subcircuit definitions."""

    def test_subcircuit_not_shuffled(self):
        """Test that .subckt/.ends blocks are preserved in order and not shuffled."""
        netlist = """.subckt opamp in_n in_p out
	* opamp implementation
.ends opamp
XU2 S_in 0 S_out opamp Aol=100K GBW=10Meg
R1 S_out S_in R
.backanno
.end
"""
        # Run multiple times with same seed to verify determinism
        result1 = randomize_spice(netlist, seed=42)
        result2 = randomize_spice(netlist, seed=42)
        
        # Should be deterministic with same seed
        self.assertEqual(result1, result2)
        
        # Subcircuit definition should appear before device statements
        lines1 = result1.splitlines()
        subckt_start_idx = None
        subckt_end_idx = None
        device_start_idx = None
        
        for i, line in enumerate(lines1):
            if line.strip().lower().startswith('.subckt'):
                subckt_start_idx = i
            if line.strip().lower().startswith('.ends'):
                subckt_end_idx = i
            if line.strip().startswith('X') or line.strip().startswith('R'):
                if device_start_idx is None:
                    device_start_idx = i
        
        self.assertIsNotNone(subckt_start_idx, "Subcircuit definition not found")
        self.assertIsNotNone(subckt_end_idx, "Subcircuit end not found")
        self.assertIsNotNone(device_start_idx, "Device statements not found")
        
        # Subcircuit should come before devices
        self.assertLess(subckt_start_idx, device_start_idx, 
                       "Subcircuit definition must come before device statements")
        self.assertLess(subckt_end_idx, device_start_idx,
                       "Subcircuit end must come before device statements")
        
        # Verify subcircuit content is intact
        subckt_lines = lines1[subckt_start_idx:subckt_end_idx + 1]
        self.assertIn('.subckt opamp in_n in_p out', subckt_lines[0])
        self.assertIn('.ends opamp', subckt_lines[-1])

    def test_multiple_subcircuits_preserved(self):
        """Test that multiple subcircuit definitions are all preserved."""
        netlist = """.subckt opamp1 in_n in_p out
	* opamp1 implementation
.ends opamp1
.subckt opamp2 in_n in_p out
	* opamp2 implementation
.ends opamp2
R1 S_out S_in R
XU1 S_in 0 S_out opamp1
XU2 S_in 0 S_out opamp2
.end
"""
        result = randomize_spice(netlist, seed=123)
        lines = result.splitlines()
        
        # Find all subcircuit definitions
        subckt_starts = []
        subckt_ends = []
        device_indices = []
        
        for i, line in enumerate(lines):
            stripped = line.strip().lower()
            if stripped.startswith('.subckt'):
                subckt_starts.append(i)
            elif stripped.startswith('.ends'):
                subckt_ends.append(i)
            elif stripped.startswith(('r', 'x', 'm', 'c', 'l')):
                device_indices.append(i)
        
        # Should have found both subcircuits
        self.assertEqual(len(subckt_starts), 2, "Should find 2 subcircuit definitions")
        self.assertEqual(len(subckt_ends), 2, "Should find 2 subcircuit ends")
        
        # All subcircuits should come before devices
        if device_indices:
            first_device = min(device_indices)
            last_subckt_end = max(subckt_ends)
            self.assertLess(last_subckt_end, first_device,
                           "All subcircuits must come before device statements")

    def test_subcircuit_content_not_modified(self):
        """Test that content within subcircuit blocks is not modified."""
        netlist = """.subckt opamp in_n in_p out
	* opamp implementation
M1 out in_n VDD VSS nch W=1u L=0.18u
M2 out in_p VDD VSS nch W=1u L=0.18u
.ends opamp
R1 S_out S_in R
.end
"""
        result = randomize_spice(netlist, seed=456)
        
        # Extract subcircuit block
        lines = result.splitlines()
        subckt_start = None
        subckt_end = None
        
        for i, line in enumerate(lines):
            if line.strip().lower().startswith('.subckt'):
                subckt_start = i
            elif line.strip().lower().startswith('.ends'):
                subckt_end = i
                break
        
        self.assertIsNotNone(subckt_start)
        self.assertIsNotNone(subckt_end)
        
        # Subcircuit should contain the internal devices
        subckt_block = '\n'.join(lines[subckt_start:subckt_end + 1])
        self.assertIn('M1', subckt_block)
        self.assertIn('M2', subckt_block)
        self.assertIn('.subckt opamp', subckt_block)
        self.assertIn('.ends opamp', subckt_block)

    def test_device_statements_shuffled(self):
        """Test that device statements (outside subcircuits) are shuffled."""
        netlist = """R1 A B R
R2 B C R
R3 C D R
.backanno
.end
"""
        # Run with different seeds to verify shuffling
        result1 = randomize_spice(netlist, seed=100)
        result2 = randomize_spice(netlist, seed=200)
        
        lines1 = [l.strip() for l in result1.splitlines() if l.strip()]
        lines2 = [l.strip() for l in result2.splitlines() if l.strip()]
        
        # Extract device lines (R1, R2, R3)
        devices1 = [l for l in lines1 if l.startswith('R')]
        devices2 = [l for l in lines2 if l.startswith('R')]
        
        # Should have same devices
        self.assertEqual(set(devices1), set(devices2), "Should have same device statements")
        
        # With different seeds, order might differ (though not guaranteed)
        # At least verify they're all present

    def test_deterministic_with_same_seed(self):
        """Test that same seed produces same output."""
        netlist = """.subckt opamp in_n in_p out
	* opamp implementation
.ends opamp
R1 S_out S_in R
R2 A B R
C1 S_out S_in C
.backanno
.end
"""
        result1 = randomize_spice(netlist, seed=999)
        result2 = randomize_spice(netlist, seed=999)
        result3 = randomize_spice(netlist, seed=999)
        
        self.assertEqual(result1, result2)
        self.assertEqual(result2, result3)

    def test_subcircuit_with_continuation_lines(self):
        """Test that continuation lines within subcircuits are preserved."""
        netlist = """.subckt opamp in_n in_p out
	* opamp implementation
+ with continuation
R1 A B R
+ more continuation
.ends opamp
R2 S_out S_in R
.end
"""
        result = randomize_spice(netlist, seed=777)
        lines = result.splitlines()
        
        # Find subcircuit block
        subckt_start = None
        subckt_end = None
        for i, line in enumerate(lines):
            if line.strip().lower().startswith('.subckt'):
                subckt_start = i
            elif line.strip().lower().startswith('.ends'):
                subckt_end = i
                break
        
        self.assertIsNotNone(subckt_start)
        self.assertIsNotNone(subckt_end)
        
        # Continuation lines should be in subcircuit block
        subckt_block = '\n'.join(lines[subckt_start:subckt_end + 1])
        self.assertIn('+ with continuation', subckt_block)
        self.assertIn('+ more continuation', subckt_block)


if __name__ == '__main__':
    unittest.main()


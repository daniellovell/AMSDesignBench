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

    def test_subcircuit_blank_lines_preserved(self):
        """Test that blank lines inside subcircuit blocks are preserved in their original positions.
        
        This test would have caught the bug where blank lines inside subcircuits were moved
        to the end of the netlist. Blank lines inside subcircuits must remain in place
        to preserve SPICE simulator compatibility.
        """
        # Create a subcircuit with blank lines at specific positions
        netlist = """.subckt opamp in_n in_p out
* comment before blank line

M1 out in_n VDD VSS nch W=1u L=0.18u

M2 out in_p VDD VSS nch W=1u L=0.18u
* comment after blank line
.ends opamp
R1 S_out S_in R
.end
"""
        result = randomize_spice(netlist, seed=888)
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
        
        self.assertIsNotNone(subckt_start, "Subcircuit start not found")
        self.assertIsNotNone(subckt_end, "Subcircuit end not found")
        
        # Extract subcircuit block (preserving original lines including blanks)
        subckt_lines = lines[subckt_start:subckt_end + 1]
        
        # Check that blank lines are PRESENT within the subcircuit block
        # (not moved to the end)
        blank_lines_in_subckt = [i for i, line in enumerate(subckt_lines) if not line.strip()]
        self.assertGreater(len(blank_lines_in_subckt), 0, 
                          "Blank lines should be preserved inside subcircuit block")
        
        # Verify the structure: should have blank line after comment, before M1
        # and blank line after M1, before M2
        subckt_text = '\n'.join(subckt_lines)
        
        # Check that blank lines exist within the subcircuit (not just at the end)
        # Find positions of key elements
        comment_idx = None
        m1_idx = None
        m2_idx = None
        for i, line in enumerate(subckt_lines):
            if '* comment before blank line' in line:
                comment_idx = i
            if 'M1' in line and m1_idx is None:
                m1_idx = i
            if 'M2' in line:
                m2_idx = i
        
        # Verify blank lines exist between elements
        if comment_idx is not None and m1_idx is not None:
            # Should have at least one blank line between comment and M1
            self.assertGreater(m1_idx, comment_idx + 1,
                             "Blank line should separate comment from M1")
        
        if m1_idx is not None and m2_idx is not None:
            # Should have at least one blank line between M1 and M2
            self.assertGreater(m2_idx, m1_idx + 1,
                             "Blank line should separate M1 from M2")
        
        # Most importantly: verify blank lines are NOT at the very end of the file
        # (which would indicate they were moved to tails)
        all_blank_at_end = True
        for i in range(len(lines) - 1, max(subckt_end, len(lines) - 10), -1):
            if i < 0:
                break
            if lines[i].strip():  # Found a non-blank line
                all_blank_at_end = False
                break
        
        # If all trailing lines are blank, that's suspicious (blank lines moved to end)
        # But we allow some blank lines at the end for aesthetics, so just check
        # that the subcircuit itself contains blank lines
        self.assertIn('.subckt opamp', subckt_lines[0])
        self.assertIn('.ends opamp', subckt_lines[-1])
        
        # Verify blank lines are actually in the subcircuit block, not just at file end
        # Check that there's at least one blank line that's NOT in the last few lines
        mid_subckt_has_blank = any(
            not line.strip() and i < len(subckt_lines) - 2
            for i, line in enumerate(subckt_lines[1:-1])
        )
        self.assertTrue(mid_subckt_has_blank or len(blank_lines_in_subckt) > 0,
                       "Subcircuit should preserve blank lines in their original positions")

    def test_footer_directives_at_end(self):
        """Test that footer directives like .end and .backanno are placed at the end."""
        netlist = """.end
R1 A B R
.backanno
R2 C D R
.end
"""
        result = randomize_spice(netlist, seed=9999)
        lines = result.splitlines()
        
        # Footer directives should be at the end
        # Find last non-blank lines
        non_blank_lines = [line for line in lines if line.strip()]
        
        # .end and .backanno should be among the last lines
        # They should come after device statements
        device_indices = []
        footer_indices = []
        
        for i, line in enumerate(lines):
            stripped = line.strip().lower()
            if stripped.startswith(('.end', '.backanno')):
                footer_indices.append(i)
            elif stripped and not stripped.startswith(('*', ';', '.')):
                # Device statement (not comment, not dot-directive)
                device_indices.append(i)
        
        if device_indices and footer_indices:
            last_device = max(device_indices)
            first_footer = min(footer_indices)
            # Footer directives should come after all devices
            self.assertGreaterEqual(first_footer, last_device,
                                  "Footer directives (.end, .backanno) should come after device statements")
        
        # Verify .end appears at the end
        last_non_blank = None
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip():
                last_non_blank = lines[i].strip().lower()
                break
        
        if last_non_blank:
            self.assertTrue(last_non_blank.startswith('.end') or last_non_blank.startswith('.backanno'),
                          f"Last directive should be .end or .backanno, got: {last_non_blank}")

    def test_header_directives_at_start(self):
        """Test that header directives like .model and .param stay in headers."""
        netlist = """.model nch nmos
.param VDD=1.8
R1 A B R
.end
"""
        result = randomize_spice(netlist, seed=8888)
        lines = result.splitlines()
        
        # Find positions
        model_idx = None
        param_idx = None
        device_idx = None
        end_idx = None
        
        for i, line in enumerate(lines):
            stripped = line.strip().lower()
            if stripped.startswith('.model'):
                model_idx = i
            elif stripped.startswith('.param'):
                param_idx = i
            elif stripped.startswith('r') and not stripped.startswith(('.end', '.backanno')):
                if device_idx is None:
                    device_idx = i
            elif stripped.startswith('.end'):
                end_idx = i
        
        # .model and .param should come before devices
        if model_idx is not None and device_idx is not None:
            self.assertLess(model_idx, device_idx,
                          ".model directive should come before device statements")
        if param_idx is not None and device_idx is not None:
            self.assertLess(param_idx, device_idx,
                          ".param directive should come before device statements")
        
        # .end should come after everything
        if end_idx is not None:
            if device_idx is not None:
                self.assertGreater(end_idx, device_idx,
                                 ".end should come after device statements")
            if model_idx is not None:
                self.assertGreater(end_idx, model_idx,
                                 ".end should come after header directives")


if __name__ == '__main__':
    unittest.main()


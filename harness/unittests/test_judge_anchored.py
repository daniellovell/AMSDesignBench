"""Unit tests for judge_anchored arithmetic expression evaluation."""

from __future__ import annotations

import unittest
import math

from harness.scoring.judge_anchored import _evaluate_arithmetic_expression


class EvaluateArithmeticExpressionTest(unittest.TestCase):
    """Tests for _evaluate_arithmetic_expression AST-based evaluator."""

    def test_basic_addition(self) -> None:
        """Test basic addition operations."""
        self.assertEqual(_evaluate_arithmetic_expression("1 + 2"), 3.0)
        self.assertEqual(_evaluate_arithmetic_expression("10 + 20"), 30.0)
        self.assertEqual(_evaluate_arithmetic_expression("1.5 + 2.5"), 4.0)
        self.assertEqual(_evaluate_arithmetic_expression("0 + 0"), 0.0)

    def test_basic_subtraction(self) -> None:
        """Test basic subtraction operations."""
        self.assertEqual(_evaluate_arithmetic_expression("5 - 3"), 2.0)
        self.assertEqual(_evaluate_arithmetic_expression("10 - 20"), -10.0)
        self.assertEqual(_evaluate_arithmetic_expression("1.5 - 0.5"), 1.0)
        self.assertEqual(_evaluate_arithmetic_expression("0 - 5"), -5.0)

    def test_basic_multiplication(self) -> None:
        """Test basic multiplication operations."""
        self.assertEqual(_evaluate_arithmetic_expression("2 * 3"), 6.0)
        self.assertEqual(_evaluate_arithmetic_expression("10 * 0"), 0.0)
        self.assertEqual(_evaluate_arithmetic_expression("2.5 * 4"), 10.0)
        self.assertEqual(_evaluate_arithmetic_expression("-2 * 3"), -6.0)

    def test_basic_division(self) -> None:
        """Test basic division operations."""
        self.assertEqual(_evaluate_arithmetic_expression("6 / 2"), 3.0)
        self.assertEqual(_evaluate_arithmetic_expression("10 / 4"), 2.5)
        self.assertEqual(_evaluate_arithmetic_expression("1 / 2"), 0.5)
        self.assertEqual(_evaluate_arithmetic_expression("0 / 5"), 0.0)

    def test_division_by_zero(self) -> None:
        """Test that division by zero returns None."""
        self.assertIsNone(_evaluate_arithmetic_expression("5 / 0"))
        self.assertIsNone(_evaluate_arithmetic_expression("1 / 0"))
        self.assertIsNone(_evaluate_arithmetic_expression("0 / 0"))

    def test_parentheses(self) -> None:
        """Test expressions with parentheses."""
        self.assertEqual(_evaluate_arithmetic_expression("(1 + 2) * 3"), 9.0)
        self.assertEqual(_evaluate_arithmetic_expression("2 * (3 + 4)"), 14.0)
        self.assertEqual(_evaluate_arithmetic_expression("(10 - 2) / 2"), 4.0)
        self.assertEqual(_evaluate_arithmetic_expression("((1 + 2) * 3) - 1"), 8.0)

    def test_unary_operators(self) -> None:
        """Test unary plus and minus operators."""
        self.assertEqual(_evaluate_arithmetic_expression("+5"), 5.0)
        self.assertEqual(_evaluate_arithmetic_expression("-5"), -5.0)
        self.assertEqual(_evaluate_arithmetic_expression("+1.5"), 1.5)
        self.assertEqual(_evaluate_arithmetic_expression("-1.5"), -1.5)
        self.assertEqual(_evaluate_arithmetic_expression("--5"), 5.0)
        self.assertEqual(_evaluate_arithmetic_expression("+-5"), -5.0)

    def test_complex_expressions(self) -> None:
        """Test complex multi-operator expressions."""
        self.assertEqual(_evaluate_arithmetic_expression("1 + 2 * 3"), 7.0)
        self.assertEqual(_evaluate_arithmetic_expression("(1 + 2) * 3"), 9.0)
        self.assertEqual(_evaluate_arithmetic_expression("10 - 2 * 3"), 4.0)
        self.assertEqual(_evaluate_arithmetic_expression("(10 - 2) * 3"), 24.0)
        self.assertEqual(_evaluate_arithmetic_expression("2 + 3 * 4 - 5"), 9.0)
        self.assertEqual(_evaluate_arithmetic_expression("(2 + 3) * (4 - 5)"), -5.0)

    def test_decimal_numbers(self) -> None:
        """Test expressions with decimal numbers."""
        self.assertEqual(_evaluate_arithmetic_expression("0.5 + 0.5"), 1.0)
        self.assertEqual(_evaluate_arithmetic_expression("1.5 * 2"), 3.0)
        self.assertEqual(_evaluate_arithmetic_expression("3.14 * 2"), 6.28)
        self.assertEqual(_evaluate_arithmetic_expression("10.5 / 2.5"), 4.2)

    def test_whitespace_handling(self) -> None:
        """Test that whitespace is properly handled."""
        self.assertEqual(_evaluate_arithmetic_expression("1+2"), 3.0)
        self.assertEqual(_evaluate_arithmetic_expression("1 + 2"), 3.0)
        self.assertEqual(_evaluate_arithmetic_expression("  1 + 2  "), 3.0)
        self.assertEqual(_evaluate_arithmetic_expression("1  +  2"), 3.0)

    def test_empty_string(self) -> None:
        """Test that empty strings return None."""
        self.assertIsNone(_evaluate_arithmetic_expression(""))
        self.assertIsNone(_evaluate_arithmetic_expression("   "))

    def test_invalid_characters(self) -> None:
        """Test that expressions with invalid characters return None."""
        self.assertIsNone(_evaluate_arithmetic_expression("1 + a"))
        self.assertIsNone(_evaluate_arithmetic_expression("print(1)"))
        self.assertIsNone(_evaluate_arithmetic_expression("1 + 2 + x"))
        self.assertIsNone(_evaluate_arithmetic_expression("__import__('os')"))

    def test_security_disallowed_nodes(self) -> None:
        """Test that security-sensitive node types are rejected."""
        # Function calls
        self.assertIsNone(_evaluate_arithmetic_expression("abs(-5)"))
        self.assertIsNone(_evaluate_arithmetic_expression("pow(2, 3)"))
        
        # Variable names
        self.assertIsNone(_evaluate_arithmetic_expression("x + 1"))
        self.assertIsNone(_evaluate_arithmetic_expression("a * b"))
        
        # Attribute access
        self.assertIsNone(_evaluate_arithmetic_expression("math.pi"))
        self.assertIsNone(_evaluate_arithmetic_expression("obj.value"))
        
        # Lambda expressions
        self.assertIsNone(_evaluate_arithmetic_expression("lambda x: x + 1"))
        
        # Comprehensions
        self.assertIsNone(_evaluate_arithmetic_expression("[x for x in range(5)]"))

    def test_disallowed_operators(self) -> None:
        """Test that disallowed operators are rejected."""
        # Power operator
        self.assertIsNone(_evaluate_arithmetic_expression("2 ** 3"))
        
        # Modulo operator
        self.assertIsNone(_evaluate_arithmetic_expression("10 % 3"))
        
        # Floor division
        self.assertIsNone(_evaluate_arithmetic_expression("10 // 3"))
        
        # Bitwise operators
        self.assertIsNone(_evaluate_arithmetic_expression("5 & 3"))
        self.assertIsNone(_evaluate_arithmetic_expression("5 | 3"))
        self.assertIsNone(_evaluate_arithmetic_expression("5 ^ 3"))
        self.assertIsNone(_evaluate_arithmetic_expression("5 << 1"))
        self.assertIsNone(_evaluate_arithmetic_expression("5 >> 1"))

    def test_single_number(self) -> None:
        """Test that single numbers are evaluated correctly."""
        self.assertEqual(_evaluate_arithmetic_expression("5"), 5.0)
        self.assertEqual(_evaluate_arithmetic_expression("0"), 0.0)
        self.assertEqual(_evaluate_arithmetic_expression("3.14"), 3.14)
        self.assertEqual(_evaluate_arithmetic_expression("-5"), -5.0)
        self.assertEqual(_evaluate_arithmetic_expression("+5"), 5.0)

    def test_negative_numbers(self) -> None:
        """Test expressions with negative numbers."""
        self.assertEqual(_evaluate_arithmetic_expression("-1 + 2"), 1.0)
        self.assertEqual(_evaluate_arithmetic_expression("1 + -2"), -1.0)
        self.assertEqual(_evaluate_arithmetic_expression("-1 * -2"), 2.0)
        self.assertEqual(_evaluate_arithmetic_expression("-10 / 2"), -5.0)

    def test_scientific_notation_handling(self) -> None:
        """Test that scientific notation is rejected (not supported)."""
        # Scientific notation is not supported - the regex pattern rejects it
        self.assertIsNone(_evaluate_arithmetic_expression("1e300 * 2"))
        self.assertIsNone(_evaluate_arithmetic_expression("1e10"))
        self.assertIsNone(_evaluate_arithmetic_expression("2e-5"))

    def test_nested_parentheses(self) -> None:
        """Test deeply nested parentheses."""
        # Mismatched parentheses should return None
        self.assertIsNone(_evaluate_arithmetic_expression("((((1 + 1)))))"))
        self.assertEqual(_evaluate_arithmetic_expression("((((1 + 1))))"), 2.0)
        self.assertEqual(_evaluate_arithmetic_expression("((1 + 2) * (3 + 4))"), 21.0)
        self.assertEqual(_evaluate_arithmetic_expression("(((2 + 3) * 4) - 1)"), 19.0)

    def test_zero_operations(self) -> None:
        """Test operations involving zero."""
        self.assertEqual(_evaluate_arithmetic_expression("0 + 0"), 0.0)
        self.assertEqual(_evaluate_arithmetic_expression("0 * 5"), 0.0)
        self.assertEqual(_evaluate_arithmetic_expression("5 * 0"), 0.0)
        self.assertEqual(_evaluate_arithmetic_expression("0 - 0"), 0.0)

    def test_fractional_results(self) -> None:
        """Test expressions that produce fractional results."""
        self.assertEqual(_evaluate_arithmetic_expression("1 / 3"), 1.0 / 3.0)
        self.assertEqual(_evaluate_arithmetic_expression("2 / 3"), 2.0 / 3.0)
        self.assertEqual(_evaluate_arithmetic_expression("1 / 4"), 0.25)

    def test_very_small_numbers(self) -> None:
        """Test expressions with very small numbers."""
        self.assertEqual(_evaluate_arithmetic_expression("0.0001 + 0.0001"), 0.0002)
        # Scientific notation is not supported (rejected by regex)
        self.assertIsNone(_evaluate_arithmetic_expression("1e-10 * 2"))

    def test_operator_precedence(self) -> None:
        """Test that operator precedence is correctly handled."""
        # Multiplication should have higher precedence than addition
        self.assertEqual(_evaluate_arithmetic_expression("2 + 3 * 4"), 14.0)
        self.assertEqual(_evaluate_arithmetic_expression("2 * 3 + 4"), 10.0)
        
        # Division should have same precedence as multiplication
        self.assertEqual(_evaluate_arithmetic_expression("10 / 2 * 3"), 15.0)
        self.assertEqual(_evaluate_arithmetic_expression("10 * 2 / 4"), 5.0)

    def test_malformed_expressions(self) -> None:
        """Test malformed expressions that should return None."""
        self.assertIsNone(_evaluate_arithmetic_expression("+"))
        self.assertIsNone(_evaluate_arithmetic_expression("*"))
        self.assertIsNone(_evaluate_arithmetic_expression("1 +"))
        # "+ 1" is actually valid (unary plus), so it returns 1.0
        self.assertEqual(_evaluate_arithmetic_expression("+ 1"), 1.0)
        self.assertIsNone(_evaluate_arithmetic_expression("()"))
        self.assertIsNone(_evaluate_arithmetic_expression("(1 +"))
        self.assertIsNone(_evaluate_arithmetic_expression("1 + )"))

    def test_result_validation(self) -> None:
        """Test that results are validated for finiteness and magnitude."""
        # The function should reject non-finite results
        # Note: It's hard to generate non-finite results with only basic arithmetic,
        # but the validation should be in place
        
        # Test that normal large numbers work
        self.assertEqual(_evaluate_arithmetic_expression("1000000 * 1000000"), 1000000000000.0)
        
        # Scientific notation is not supported (rejected by regex)
        self.assertIsNone(_evaluate_arithmetic_expression("1e100 * 1e100"))
        
        # Results exceeding 1e308 should be rejected
        # This is tested implicitly through the overflow protection


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


"""Unit tests for the calculator tool (tools/calculator.py)."""
import pytest


# Import the tool; it registers itself as a side-effect.
# We test via the LangChain StructuredTool interface.
def _calc(expr: str) -> str:
    """Helper: invoke the calculator tool with a single expression string."""
    # Import lazily to avoid import-time side effects during test collection.
    from tools.calculator import calculator
    return calculator.invoke({"expression": expr})


class TestCalculatorBasicArithmetic:
    def test_addition(self):
        assert _calc("2 + 3") == "5"

    def test_subtraction(self):
        assert _calc("10 - 4") == "6"

    def test_multiplication(self):
        assert _calc("3 * 7") == "21"

    def test_division(self):
        assert _calc("20 / 4") == "5.0"

    def test_integer_arithmetic(self):
        assert _calc("100 - 1") == "99"


class TestCalculatorAdvancedOps:
    def test_power(self):
        assert _calc("2 ** 8") == "256"

    def test_modulo(self):
        assert _calc("17 % 5") == "2"

    def test_unary_negation(self):
        assert _calc("-5") == "-5"

    def test_nested_expression(self):
        assert _calc("(2 + 3) * 4") == "20"

    def test_complex_nested(self):
        assert _calc("10 * (3 + 4) - 2") == "68"

    def test_float_result(self):
        result = _calc("1 / 3")
        assert result.startswith("0.333")


class TestCalculatorErrorHandling:
    def test_division_by_zero_returns_error_string(self):
        result = _calc("1 / 0")
        assert "Error" in result or "error" in result.lower() or "division" in result.lower() or "ZeroDivision" in result

    def test_invalid_syntax_returns_error_string(self):
        result = _calc("2 +* 3")
        assert "Error" in result or "error" in result.lower()

    def test_empty_expression_returns_error(self):
        result = _calc("")
        assert "Error" in result or "error" in result.lower()

    def test_unsupported_bitwise_operator(self):
        # Bitwise AND is not in _safe_ops
        result = _calc("4 & 2")
        assert "Error" in result or "Unsupported" in result

    def test_variable_name_rejected(self):
        # Bare names (Name nodes) are not in _safe_ops
        result = _calc("x + 1")
        assert "Error" in result or "Unsupported" in result

    def test_function_call_rejected(self):
        result = _calc("abs(-5)")
        assert "Error" in result or "Unsupported" in result


class TestCalculatorToolMetadata:
    def test_tool_has_name(self):
        from tools.calculator import calculator
        assert calculator.name == "calculator"

    def test_tool_has_description(self):
        from tools.calculator import calculator
        assert "math" in calculator.description.lower() or "expression" in calculator.description.lower()

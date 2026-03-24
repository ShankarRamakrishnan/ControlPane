import ast
import operator
from langchain_core.tools import tool
from gateway.core.tool_registry import register


@register
@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression safely. Input: a math expression string like '2 + 2' or '10 * (3 + 4)'."""
    _safe_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
    }

    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in _safe_ops:
                raise ValueError(f"Unsupported operator: {op_type}")
            return _safe_ops[op_type](_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in _safe_ops:
                raise ValueError(f"Unsupported operator: {op_type}")
            return _safe_ops[op_type](_eval(node.operand))
        else:
            raise ValueError(f"Unsupported expression node: {type(node)}")

    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _eval(tree.body)
        return str(result)
    except Exception as e:
        return f"Error evaluating expression: {e}"

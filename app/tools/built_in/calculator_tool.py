"""Calculator Tool - allows agents to perform mathematical calculations."""
import json
import math
from typing import Union
from app.tools.base_tool import BaseTool, ToolOutput


class CalculatorTool(BaseTool):
    """Tool for mathematical calculations."""

    def __init__(self):
        """Initialize calculator tool."""
        super().__init__(
            name="calculator",
            description="Perform mathematical calculations (addition, subtraction, multiplication, division, power, sqrt, etc.)"
        )

    def get_schema(self) -> dict:
        """Get JSON schema for calculator inputs."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide", "power", "sqrt", "factorial", "average"],
                    "description": "Mathematical operation to perform"
                },
                "values": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Numbers to perform operation on"
                }
            },
            "required": ["operation", "values"]
        }

    async def execute(
        self,
        operation: str,
        values: list[Union[int, float]],
        **kwargs
    ) -> ToolOutput:
        """
        Execute mathematical operation.
        
        Args:
            operation: Operation name (add, subtract, etc.)
            values: List of numbers
            
        Returns:
            ToolOutput with result or error
        """
        try:
            # Validate inputs
            if not values or len(values) == 0:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="values cannot be empty"
                )
            
            operation = operation.lower().strip()
            
            # Perform operation
            if operation == "add":
                result = sum(values)
            elif operation == "subtract":
                if len(values) < 2:
                    return ToolOutput(success=False, result=None, error="subtract requires at least 2 values")
                result = values[0] - sum(values[1:])
            elif operation == "multiply":
                result = 1
                for v in values:
                    result *= v
            elif operation == "divide":
                if len(values) < 2:
                    return ToolOutput(success=False, result=None, error="divide requires at least 2 values")
                result = values[0]
                for v in values[1:]:
                    if v == 0:
                        return ToolOutput(success=False, result=None, error="Division by zero")
                    result /= v
            elif operation == "power":
                if len(values) != 2:
                    return ToolOutput(success=False, result=None, error="power requires exactly 2 values")
                result = values[0] ** values[1]
            elif operation == "sqrt":
                if len(values) != 1:
                    return ToolOutput(success=False, result=None, error="sqrt requires exactly 1 value")
                if values[0] < 0:
                    return ToolOutput(success=False, result=None, error="Cannot take sqrt of negative number")
                result = math.sqrt(values[0])
            elif operation == "factorial":
                if len(values) != 1:
                    return ToolOutput(success=False, result=None, error="factorial requires exactly 1 value")
                if values[0] < 0 or values[0] != int(values[0]):
                    return ToolOutput(success=False, result=None, error="factorial requires non-negative integer")
                result = math.factorial(int(values[0]))
            elif operation == "average":
                result = sum(values) / len(values)
            else:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Unknown operation: {operation}"
                )
            
            return ToolOutput(success=True, result={"result": result, "operation": operation})
            
        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Calculation error: {str(e)}"
            )

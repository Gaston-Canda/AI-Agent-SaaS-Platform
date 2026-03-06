"""Built-in tools for agents."""
from app.tools.built_in.http_request_tool import HTTPRequestTool
from app.tools.built_in.calculator_tool import CalculatorTool
from app.tools.built_in.database_tool import DatabaseQueryTool
from app.tools.database_tool import DatabaseTool
from app.tools.http_tool import HTTPTool
from app.tools.search_tool import SearchTool

__all__ = [
    "HTTPRequestTool",
    "CalculatorTool",
    "DatabaseQueryTool",
    "DatabaseTool",
    "HTTPTool",
    "SearchTool",
]

# Convenience function to register all built-in tools
def register_builtin_tools(registry):
    """Register all built-in tools to a registry."""
    registry.register(HTTPRequestTool())
    registry.register(CalculatorTool())
    registry.register(DatabaseQueryTool())
    registry.register(DatabaseTool())
    registry.register(HTTPTool())
    registry.register(SearchTool())

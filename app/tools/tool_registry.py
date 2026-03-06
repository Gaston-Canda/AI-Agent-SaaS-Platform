"""Tool Registry for managing available tools."""
from typing import Optional
from app.tools.base_tool import BaseTool


class ToolRegistry:
    """
    Registry of all available tools that agents can use.
    
    Tools are registered once and can be loaded by agents based on configuration.
    """

    _tools: dict[str, BaseTool] = {}
    _loading_error_tolerance = True  # Continue even if some tools fail to load

    @classmethod
    def register(cls, tool: BaseTool) -> None:
        """
        Register a tool.
        
        Args:
            tool: BaseTool instance
            
        Raises:
            ValueError: If tool name already registered
        """
        if tool.name in cls._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        cls._tools[tool.name] = tool

    @classmethod
    def register_multiple(cls, tools: list[BaseTool], ignore_duplicates: bool = False) -> None:
        """
        Register multiple tools at once.
        
        Args:
            tools: List of BaseTool instances
            ignore_duplicates: If True, skip duplicates instead of raising
        """
        for tool in tools:
            try:
                cls.register(tool)
            except ValueError as e:
                if not ignore_duplicates:
                    raise
                # Log and continue if ignoring duplicates

    @classmethod
    def get_tool(cls, name: str) -> Optional[BaseTool]:
        """
        Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            BaseTool instance or None if not found
        """
        return cls._tools.get(name)

    @classmethod
    def get_tools(cls, names: list[str]) -> dict[str, BaseTool]:
        """
        Get multiple tools by names.
        
        Args:
            names: List of tool names
            
        Returns:
            Dict mapping tool names to BaseTool instances.
            Only includes tools that were found.
        """
        result = {}
        for name in names:
            tool = cls.get_tool(name)
            if tool:
                result[name] = tool
        return result

    @classmethod
    def list_tools(cls) -> list[str]:
        """Get list of all registered tool names."""
        return list(cls._tools.keys())

    @classmethod
    def get_tools_for_llm(cls, tool_names: list[str]) -> list[dict]:
        """
        Get tools in format expected by LLMs.
        
        Args:
            tool_names: List of tool names
            
        Returns:
            List of dicts with tool info suitable for LLM tool calling
        """
        result = []
        for name in tool_names:
            tool = cls.get_tool(name)
            if tool:
                result.append(tool.to_llm_dict())
        return result

    @classmethod
    def get_tool_info(cls, tool_name: str) -> Optional[dict]:
        """Get detailed info about a tool."""
        tool = cls.get_tool(tool_name)
        return tool.get_info() if tool else None

    @classmethod
    def clear(cls) -> None:
        """Clear all registered tools. Useful for testing."""
        cls._tools.clear()

    @classmethod
    def validate_tools_exist(cls, names: list[str]) -> tuple[bool, list[str]]:
        """
        Validate that all tools exist.
        
        Args:
            names: Tool names to validate
            
        Returns:
            Tuple of (all_exist: bool, missing_names: list[str])
        """
        missing = [n for n in names if n not in cls._tools]
        return len(missing) == 0, missing

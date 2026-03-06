"""Base class for all tools."""
from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel


class ToolInput(BaseModel):
    """Input for a tool execution."""
    pass


class ToolOutput(BaseModel):
    """Output from a tool execution."""
    success: bool
    result: Any
    error: Optional[str] = None


class BaseTool(ABC):
    """
    Abstract base class for all tools that agents can use.
    
    Tools are actions/functions that agents can execute to interact
    with external systems (HTTP, databases, etc.)
    """

    def __init__(self, name: str, description: str):
        """
        Initialize a tool.
        
        Args:
            name: Unique name of the tool
            description: Human-readable description of what the tool does
        """
        self.name = name
        self.description = description

    @abstractmethod
    def get_schema(self) -> dict:
        """
        Get JSON schema for this tool's inputs.
        
        Returns:
            Dict with 'type', 'properties', 'required' keys.
            Used by LLMs to understand how to call the tool.
            
        Example:
            {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "HTTP URL"},
                    "method": {"type": "string", "enum": ["GET", "POST"]}
                },
                "required": ["url"]
            }
        """
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> ToolOutput:
        """
        Execute the tool with given parameters.
        
        Args:
            **kwargs: Tool-specific input parameters
            
        Returns:
            ToolOutput with success status and result/error
        """
        pass

    def to_llm_dict(self) -> dict:
        """Convert tool to format expected by LLMs."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.get_schema()
        }

    def get_info(self) -> dict:
        """Get tool information."""
        return {
            "name": self.name,
            "description": self.description,
            "schema": self.get_schema()
        }

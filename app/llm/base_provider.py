"""Base class for all LLM providers."""
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel


class LLMMessage(BaseModel):
    """Represents a message in a conversation."""
    role: str  # "system", "user", "assistant"
    content: str


class LLMResponse(BaseModel):
    """Response from an LLM provider."""
    content: str
    stop_reason: Optional[str] = None  # "stop", "tool_use", etc.
    tool_calls: Optional[list] = None  # List of tool calls if any
    usage: Optional[dict] = None  # Token usage: {"prompt_tokens": 100, "completion_tokens": 50}


class ToolCall(BaseModel):
    """Represents a tool call requested by the LLM."""
    tool_name: str
    tool_input: dict
    tool_use_id: Optional[str] = None  # For multi-turn tool execution


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All LLM providers must inherit from this class and implement
    the required methods.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, **kwargs):
        """
        Initialize the LLM provider.
        
        Args:
            api_key: API key for the provider (if needed)
            model: Model name/ID to use
            **kwargs: Additional provider-specific arguments
        """
        self.api_key = api_key
        self.model = model
        self.config = kwargs

    @abstractmethod
    async def call(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[list] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Call the LLM with a list of messages.
        
        Args:
            messages: List of LLMMessage objects
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            tools: List of available tools (for tool calling)
            **kwargs: Additional provider-specific arguments
            
        Returns:
            LLMResponse with the model's response
        """
        pass

    @abstractmethod
    async def validate_connection(self) -> bool:
        """
        Validate that the provider can connect and authenticate.
        
        Returns:
            True if connection is valid, False otherwise
        """
        pass

    @staticmethod
    def parse_tool_calls(response: LLMResponse) -> list[ToolCall]:
        """
        Parse tool calls from the LLM response.
        
        Each provider may format tool calls differently,
        but they should all return a list of ToolCall objects.
        
        Args:
            response: LLMResponse from the provider
            
        Returns:
            List of ToolCall objects
        """
        return response.tool_calls or []

    def get_info(self) -> dict:
        """Get provider information."""
        return {
            "provider": self.__class__.__name__,
            "model": self.model,
            "config": self.config
        }

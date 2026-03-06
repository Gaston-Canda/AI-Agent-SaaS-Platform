"""Anthropic Claude LLM Provider."""
import os
import json
from typing import Optional
import httpx
from app.llm.base_provider import BaseLLMProvider, LLMMessage, LLMResponse


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude 2/3 provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-opus-20240229",
        **kwargs
    ):
        """Initialize Anthropic provider."""
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not provided and not found in environment")
        
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.base_url = "https://api.anthropic.com/v1"
        self.api_version = "2024-01-15"

    def _format_messages(self, messages: list[LLMMessage]) -> tuple[str, list[dict]]:
        """
        Format messages for Anthropic API.
        
        Anthropic uses system prompt separately from messages.
        Returns: (system_prompt, formatted_messages)
        """
        system_prompt = ""
        formatted_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_prompt += msg.content + "\n"
            else:
                formatted_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        return system_prompt.strip(), formatted_messages

    def _format_tools(self, tools: Optional[list]) -> Optional[list]:
        """Format tools for Anthropic tool use."""
        if not tools:
            return None
        
        formatted = []
        for tool in tools:
            formatted.append({
                "name": tool.get("name"),
                "description": tool.get("description"),
                "input_schema": {
                    "type": "object",
                    "properties": tool.get("parameters", {}).get("properties", {}),
                    "required": tool.get("parameters", {}).get("required", [])
                }
            })
        return formatted

    def _parse_response(self, response_data: dict) -> LLMResponse:
        """Parse Anthropic API response."""
        content = ""
        tool_calls = None
        stop_reason = response_data.get("stop_reason")
        
        # Process content blocks
        if "content" in response_data:
            blocks = response_data["content"]
            tool_calls = []
            
            for block in blocks:
                if block.get("type") == "text":
                    content += block.get("text", "")
                elif block.get("type") == "tool_use":
                    tool_calls.append({
                        "tool_name": block.get("name"),
                        "tool_input": block.get("input", {}),
                        "tool_use_id": block.get("id")
                    })
        
        # Remove empty tool_calls list if no tools were used
        if tool_calls and len(tool_calls) == 0:
            tool_calls = None
        
        usage = response_data.get("usage", {})
        
        return LLMResponse(
            content=content,
            stop_reason=stop_reason,
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            }
        )

    async def call(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[list] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Call Anthropic API.
        
        Args:
            messages: List of LLMMessage objects
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: List of tools for tool use
            **kwargs: Additional arguments
            
        Returns:
            LLMResponse
        """
        system_prompt, formatted_messages = self._format_messages(messages)
        
        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 2048
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        if tools:
            payload["tools"] = self._format_tools(tools)
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "content-type": "application/json"
        }
        
        timeout = kwargs.get("timeout", 60)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/messages",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            response_data = response.json()
            return self._parse_response(response_data)

    async def validate_connection(self) -> bool:
        """Validate Anthropic API connection."""
        try:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": self.api_version,
                "content-type": "application/json"
            }
            
            # Try to list models as a validation check
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=headers
                )
                return response.status_code == 200
        except Exception:
            return False

"""OpenAI LLM Provider."""
import os
import json
from typing import Optional
import httpx
from app.llm.base_provider import BaseLLMProvider, LLMMessage, LLMResponse, ToolCall
from app.core.config import settings


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT-4, GPT-3.5 turbo provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        organization_id: Optional[str] = None,
        **kwargs
    ):
        """Initialize OpenAI provider."""
        api_key = api_key or settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not provided and not found in environment")
        model = model or settings.OPENAI_MODEL
        
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.organization_id = organization_id
        self.base_url = "https://api.openai.com/v1"
        self.client = None

    def _format_messages(self, messages: list[LLMMessage]) -> list[dict]:
        """Format messages for OpenAI API."""
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def _format_tools(self, tools: Optional[list]) -> Optional[list]:
        """Format tools for OpenAI function calling."""
        if not tools:
            return None
        
        formatted = []
        for tool in tools:
            formatted.append({
                "type": "function",
                "function": {
                    "name": tool.get("name"),
                    "description": tool.get("description"),
                    "parameters": tool.get("parameters", {})
                }
            })
        return formatted

    def _parse_response(self, response_data: dict) -> LLMResponse:
        """Parse OpenAI API response."""
        choice = response_data["choices"][0]
        message = choice["message"]
        content = message.get("content", "")
        stop_reason = choice.get("finish_reason")
        
        tool_calls = None
        if "tool_calls" in message:
            tool_calls = []
            for tc in message["tool_calls"]:
                parsed_args = {}
                try:
                    parsed_args = json.loads(tc["function"]["arguments"])
                except Exception:
                    parsed_args = {}
                tool_calls.append({
                    "tool_name": tc["function"]["name"],
                    "tool_input": parsed_args,
                    "tool_use_id": tc.get("id")
                })
        
        usage = response_data.get("usage", {})
        
        return LLMResponse(
            content=content,
            stop_reason=stop_reason,
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0)
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
        Call OpenAI API.
        
        Args:
            messages: List of LLMMessage objects
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: List of tools for function calling
            **kwargs: Additional arguments (timeout, etc.)
            
        Returns:
            LLMResponse
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        if self.organization_id:
            headers["OpenAI-Organization"] = self.organization_id
        
        payload = {
            "model": self.model,
            "messages": self._format_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens or 2048
        }
        
        if tools:
            payload["tools"] = self._format_tools(tools)
            payload["tool_choice"] = "auto"
        
        timeout = kwargs.get("timeout", 60)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            response_data = response.json()
            return self._parse_response(response_data)

    async def validate_connection(self) -> bool:
        """Validate OpenAI API connection."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.base_url}/models/{self.model}",
                    headers=headers
                )
                return response.status_code == 200
        except Exception:
            return False

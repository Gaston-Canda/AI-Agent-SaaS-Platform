"""LLM Provider Registry."""
from typing import Optional, Type
from app.llm.base_provider import BaseLLMProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.anthropic_provider import AnthropicProvider


class ProviderRegistry:
    """
    Registry for all available LLM providers.
    
    Allows dynamic registration and retrieval of LLM providers.
    """
    
    _providers: dict[str, Type[BaseLLMProvider]] = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
    }
    
    _instances: dict[str, BaseLLMProvider] = {}

    @classmethod
    def register(cls, name: str, provider_class: Type[BaseLLMProvider]) -> None:
        """
        Register a new LLM provider.
        
        Args:
            name: Name/key for the provider
            provider_class: Provider class (must extend BaseLLMProvider)
        """
        if not issubclass(provider_class, BaseLLMProvider):
            raise TypeError(f"{provider_class} must extend BaseLLMProvider")
        cls._providers[name] = provider_class

    @classmethod
    def get_provider(
        cls,
        name: str,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        use_cache: bool = False,
        **kwargs
    ) -> BaseLLMProvider:
        """
        Get an LLM provider instance.
        
        Args:
            name: Provider name (e.g., "openai", "anthropic")
            api_key: API key (optional, can come from env)
            model: Model name
            use_cache: Whether to cache the instance for reuse
            **kwargs: Additional provider-specific arguments
            
        Returns:
            BaseLLMProvider instance
            
        Raises:
            ValueError: If provider name is not registered
        """
        if name not in cls._providers:
            raise ValueError(
                f"Provider '{name}' not found. Available: {list(cls._providers.keys())}"
            )
        
        # Return cached instance if requested
        cache_key = f"{name}:{model or 'default'}"
        if use_cache and cache_key in cls._instances:
            return cls._instances[cache_key]
        
        # Create new instance
        provider_class = cls._providers[name]
        provider = provider_class(api_key=api_key, model=model, **kwargs)
        
        # Cache if requested
        if use_cache:
            cls._instances[cache_key] = provider
        
        return provider

    @classmethod
    def list_providers(cls) -> list[str]:
        """Get list of available provider names."""
        return list(cls._providers.keys())

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the provider instance cache."""
        cls._instances.clear()

    @classmethod
    def validate_provider(cls, name: str, api_key: Optional[str] = None) -> bool:
        """
        Validate that a provider can connect.
        
        Args:
            name: Provider name
            api_key: API key (optional)
            
        Returns:
            True if provider is valid, False otherwise
        """
        import asyncio
        try:
            provider = cls.get_provider(name, api_key=api_key)
            # Run async validation
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(provider.validate_connection())
        except Exception:
            return False

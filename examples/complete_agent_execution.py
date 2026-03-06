"""
Complete example of agent execution with all systems integrated.

This example shows how to:
1. Create agent configuration
2. Initialize memory manager
3. Execute agent with LLM providers and tools
4. Handle async execution
5. Process results and logs
"""

import asyncio
from app.engine import AgentEngine
from app.memory import MemoryManager
from app.llm import ProviderRegistry
from app.tools import ToolRegistry, register_builtin_tools


async def example_simple_chat():
    """Simple chat interaction with memory."""
    print("\n=== Example 1: Simple Chat ===\n")
    
    # Initialize
    engine = AgentEngine()
    memory = MemoryManager(memory_id="chat-001")
    register_builtin_tools(ToolRegistry)
    
    # Agent configuration
    agent_config = {
        "name": "Helpful Assistant",
        "system_prompt": "You are a helpful assistant. Answer concisely.",
        "llm_provider": "openai",
        "llm_model": "gpt-4-turbo-preview",
        "tools": [],  # No tools for simple chat
        "temperature": 0.7,
        "max_tokens": 500
    }
    
    # First interaction
    print("User: What is the capital of France?")
    result = await engine.execute(
        agent_config=agent_config,
        user_input="What is the capital of France?",
        execution_id="exec-001",
        agent_id="agent-001",
        user_id="user-001",
        tenant_id="tenant-001",
        memory_manager=memory
    )
    
    if result["success"]:
        print(f"Assistant: {result['response']}\n")
    else:
        print(f"Error: {result['error']}\n")
    
    # Second interaction (with memory)
    print("User: Tell me about its history")
    result = await engine.execute(
        agent_config=agent_config,
        user_input="Tell me about its history",
        execution_id="exec-002",
        agent_id="agent-001",
        user_id="user-001",
        tenant_id="tenant-001",
        memory_manager=memory
    )
    
    if result["success"]:
        print(f"Assistant: {result['response']}\n")
    
    # Show stats
    ctx = result["execution_context"]
    print(f"Stats:")
    print(f"  - Tokens used: {ctx.prompt_tokens + ctx.completion_tokens}")
    print(f"  - Execution time: {ctx.get_execution_time_ms()}ms")
    print(f"  - Cost: ${ctx.total_cost_usd:.4f}\n")


async def example_agent_with_tools():
    """Agent that can use tools (HTTP, calculator, database)."""
    print("\n=== Example 2: Agent with Tools ===\n")
    
    engine = AgentEngine()
    memory = MemoryManager(memory_id="agent-with-tools-001")
    register_builtin_tools(ToolRegistry)
    
    agent_config = {
        "name": "Research Bot",
        "system_prompt": """You are a research assistant. 
When asked to find information:
1. Try to use the http_request tool to fetch data
2. Use calculator tool for any calculations needed
3. Provide sources and citations
Keep responses concise.""",
        "llm_provider": "openai",
        "llm_model": "gpt-4-turbo-preview",
        "tools": ["http_request", "calculator"],  # Can use these tools
        "temperature": 0.5,
        "max_tokens": 2048
    }
    
    # Query that might need tools
    user_query = "What's 15% of 500? Also, fetch the Bitcoin price from CoinMarketCap."
    print(f"User: {user_query}\n")
    
    result = await engine.execute(
        agent_config=agent_config,
        user_input=user_query,
        execution_id="exec-tools-001",
        agent_id="agent-tools-001",
        user_id="user-001",
        tenant_id="tenant-001",
        memory_manager=memory,
        max_tool_loops=3
    )
    
    if result["success"]:
        print(f"Assistant: {result['response']}\n")
        
        # Show execution details
        ctx = result["execution_context"]
        print("Execution Details:")
        for step in ctx.steps:
            print(f"  {step.step_number}. {step.action}")
            if step.action == "execute_tool":
                print(f"     Tool: {step.details.get('tool_name')}")
                print(f"     Success: {step.success}")
        
        print(f"\nTools executed: {len(ctx.tools_executed)}")
        print(f"Tokens: {ctx.prompt_tokens + ctx.completion_tokens}")
        print(f"Time: {ctx.get_execution_time_ms()}ms")
    else:
        print(f"Error: {result['error']}\n")


async def example_provider_switching():
    """Using different LLM providers."""
    print("\n=== Example 3: Provider Switching ===\n")
    
    engine = AgentEngine()
    memory = MemoryManager(memory_id="provider-test-001")
    
    providers = [
        ("openai", "gpt-4-turbo-preview"),
        ("openai", "gpt-3.5-turbo"),
        ("anthropic", "claude-3-opus-20240229"),
    ]
    
    for provider_name, model_name in providers:
        print(f"\nTrying {provider_name}/{model_name}...")
        
        # Check if provider is registered
        if provider_name not in ProviderRegistry.list_providers():
            print(f"  ⚠️  Provider {provider_name} not registered, skipping\n")
            continue
        
        config = {
            "name": "Test Bot",
            "system_prompt": "You are a helpful bot.",
            "llm_provider": provider_name,
            "llm_model": model_name,
            "tools": [],
            "temperature": 0.7,
            "max_tokens": 200
        }
        
        # Validate config
        is_valid, error = await engine.validate_agent_config(config)
        if not is_valid:
            print(f"  ❌ Invalid: {error}\n")
            continue
        
        print(f"  ✓ Valid configuration")
        print(f"  (Skipping execution - would need API keys)\n")


async def example_memory_management():
    """Demonstrating memory system."""
    print("\n=== Example 4: Memory Management ===\n")
    
    memory = MemoryManager(memory_id="memory-demo-001")
    
    # Add messages
    print("Adding messages to memory...")
    await memory.add_message("user", "What's the weather today?")
    await memory.add_message("assistant", "It's sunny, 72°F")
    await memory.add_message("user", "Great! Any recommendations?")
    
    # Get context
    context = await memory.get_context_for_llm(max_tokens=1000)
    print(f"\nContext for LLM:\n{context}")
    
    # Search
    print("\n\nSearching for 'weather'...")
    results = await memory.search_memory("weather", use_vector=False, limit=5)
    for msg in results:
        print(f"  [{msg.role.upper()}] {msg.content}")
    
    # Summary
    print("\n\nMemory Summary:")
    summary = await memory.get_memory_summary()
    print(summary)


async def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("AI AGENTS FRAMEWORK - COMPLETE EXAMPLES")
    print("="*60)
    
    try:
        # Example 1: Simple chat
        await example_simple_chat()
        
        # Example 2: Agent with tools
        # await example_agent_with_tools()  # Uncomment when LLM is working
        
        # Example 3: Provider switching
        # await example_provider_switching()  # Uncomment to test
        
        # Example 4: Memory
        await example_memory_management()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
    print("EXAMPLES COMPLETED")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

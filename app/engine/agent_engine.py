"""Agent Engine - orchestrates agent execution."""
import time
from typing import Optional, Dict, Any, Union

from app.llm import ProviderRegistry, LLMMessage, LLMResponse
from app.llm.openai_client import generate_response_with_usage
from app.tools import ToolRegistry, ToolExecutor
from app.memory import MemoryManager, MemoryService
from app.monitoring.logging import StructuredLogger
from app.engine.execution_context import ExecutionContext


logger = StructuredLogger(__name__)


def _messages_to_prompt(messages: list[LLMMessage]) -> str:
    """Convert chat messages to a single prompt for simple OpenAI client calls."""
    prompt_parts = []
    for message in messages:
        role = message.role.upper()
        prompt_parts.append(f"{role}: {message.content}")
    return "\n\n".join(prompt_parts)


class AgentEngine:
    """
    Main orchestrator for agent execution.
    
    Flow:
    1. Load Agent Configuration
    2. Build Prompt with conversation history
    3. Call LLM Provider
    4. Execute Tools if LLM requests them
    5. Update Memory
    6. Return Final Result
    """

    def __init__(self):
        """Initialize agent engine."""
        self.provider_registry = ProviderRegistry
        self.tool_registry = ToolRegistry
        self.memory_service = MemoryService()

    async def execute(
        self,
        agent_config: Union[Dict[str, Any], "AgentConfig"],
        user_input: str,
        execution_id: str,
        agent_id: str,
        user_id: str,
        tenant_id: str,
        memory_manager: Optional[MemoryManager] = None,
        max_tool_loops: int = 5,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute an agent.
        
        Args:
            agent_config: Agent configuration (supports both formats):
                * Dict[str, Any] with keys:
                  - system_prompt: System prompt
                  - llm_provider: "openai" or "anthropic"
                  - llm_model: Model name
                  - tools: List of allowed tool names
                  - temperature: LLM temperature
                  - max_tokens: Max tokens
                  (For backward compatibility with Phase 1/2)
                
                * AgentConfig (Pydantic schema from Phase 3):
                  - agent_id, version_number
                  - system_prompt (pre-assembled)
                  - llm_config: LLMConfig with provider, model, temperature, etc.
                  - tools: List of AgentToolConfigItem
                  - prompts: AgentPromptConfigItem
                  - memory_config: AgentMemoryConfig
                  (Phase 3 dynamic configuration)
            
            user_input: User's input/prompt
            execution_id: Unique execution ID
            agent_id: Agent ID
            user_id: User ID
            tenant_id: Tenant ID
            memory_manager: Optional memory manager (for conversation history)
            max_tool_loops: Max times to loop with tools
            **kwargs: Additional arguments
            
        Returns:
            Dict with:
            - success: bool
            - response: str (final response)
            - execution_context: ExecutionContext
            - error: Optional error message
        """
        # Convert AgentConfig to dict if necessary (Phase 3 compatibility)
        if not isinstance(agent_config, dict):
            # It's an AgentConfig Pydantic model
            from app.engine.config_converter import agent_config_to_dict
            agent_config = agent_config_to_dict(agent_config)
        # Initialize execution context
        ctx = ExecutionContext(
            agent_id=agent_id,
            execution_id=execution_id,
            user_id=user_id,
            tenant_id=tenant_id
        )
        ctx.status = "running"
        
        try:
            # Step 1: Load Agent Configuration
            logger.log_execution(
                "Agent execution started",
                {"execution_id": execution_id, "agent_id": agent_id}
            )
            
            ctx.record_step(
                action="load_config",
                details={"agent_name": agent_config.get("name")},
                duration_ms=0
            )
            
            ctx.agent_config = agent_config
            ctx.llm_provider = agent_config.get("llm_provider", "openai")
            ctx.allowed_tools = agent_config.get("tools", [])
            
            # Create tool executor
            tool_executor = ToolExecutor(ctx.allowed_tools) if ctx.allowed_tools else None
            
            # Step 2: Build Initial Prompt
            system_prompt = agent_config.get("system_prompt", "You are helpful assistant.")
            db = kwargs.get("db")

            # Best-effort semantic memory retrieval (long-term)
            memory_augmentation = ""
            if db is not None:
                try:
                    similar_memories = self.memory_service.retrieve_similar_memories(
                        db=db,
                        tenant_id=tenant_id,
                        agent_id=agent_id,
                        query=user_input,
                        limit=5,
                    )
                    if similar_memories:
                        memory_augmentation = "\n".join(
                            f"- {item.content[:300]}"
                            for item in similar_memories
                        )
                except Exception as exc:
                    logger.log_error("Long-term memory retrieval failed", {"error": str(exc)})
            
            # Get conversation history if memory manager provided
            context_history = ""
            if memory_manager:
                context_history = await memory_manager.get_context_for_llm(max_tokens=2000)
            
            ctx.record_step(
                action="build_prompt",
                details={
                    "system_prompt_preview": system_prompt[:100],
                    "has_history": bool(context_history),
                    "tools_available": len(ctx.allowed_tools)
                }
            )
            
            # Step 3: Main Agentic Loop
            messages = [
                LLMMessage(role="system", content=system_prompt)
            ]
            
            # Add conversation history
            if context_history:
                messages.append(LLMMessage(role="system", content=f"Previous context:\n{context_history}"))
            if memory_augmentation:
                messages.append(
                    LLMMessage(
                        role="system",
                        content=f"Relevant long-term memories:\n{memory_augmentation}",
                    )
                )
            
            # Add user input
            messages.append(LLMMessage(role="user", content=user_input))
            
            # Add to memory
            if memory_manager:
                try:
                    await memory_manager.add_message("user", user_input)
                except Exception as exc:
                    logger.log_error("Memory manager user write failed", {"error": str(exc)})
            
            # Tool loop
            tool_loop_count = 0
            final_response = None
            
            while tool_loop_count < max_tool_loops:
                tool_loop_count += 1
                
                # Get LLM provider
                try:
                    llm_provider = self.provider_registry.get_provider(
                        ctx.llm_provider,
                        model=agent_config.get("llm_model", "gpt-4-turbo-preview")
                    )
                except Exception as e:
                    ctx.record_step(
                        action="get_llm",
                        details={"provider": ctx.llm_provider},
                        success=False,
                        error=str(e)
                    )
                    raise
                
                # Prepare tools for LLM
                llm_tools = None
                if tool_executor:
                    llm_tools = tool_executor.get_available_tools_for_llm()
                
                # Call LLM
                try:
                    llm_started = time.perf_counter()
                    # Use reusable OpenAI client for the real OpenAI provider in simple (non-tool) calls.
                    # Keep provider path for tool-calling and testing fakes/mocks.
                    if (
                        ctx.llm_provider == "openai"
                        and llm_tools is None
                        and llm_provider.__class__.__name__ == "OpenAIProvider"
                    ):
                        completion = generate_response_with_usage(_messages_to_prompt(messages))
                        llm_content = completion.response
                        llm_response = LLMResponse(
                            content=llm_content,
                            stop_reason="stop",
                            tool_calls=None,
                            usage={
                                "prompt_tokens": completion.prompt_tokens,
                                "completion_tokens": completion.completion_tokens,
                                "total_tokens": completion.total_tokens,
                            },
                        )
                    else:
                        llm_response = await llm_provider.call(
                            messages=messages,
                            temperature=agent_config.get("temperature", 0.7),
                            max_tokens=agent_config.get("max_tokens", 2048),
                            tools=llm_tools
                        )
                    llm_latency_ms = int((time.perf_counter() - llm_started) * 1000)
                    
                    # Record LLM call
                    if llm_response.usage:
                        ctx.record_llm_call(
                            prompt_tokens=llm_response.usage.get("prompt_tokens", 0),
                            completion_tokens=llm_response.usage.get("completion_tokens", 0),
                            cost_usd=0.0,  # TODO: Calculate based on model and tokens
                            response_preview=llm_response.content,
                            latency_ms=llm_latency_ms,
                        )
                    
                    # Add LLM response to messages
                    messages.append(LLMMessage(role="assistant", content=llm_response.content))
                    
                except Exception as e:
                    ctx.record_step(
                        action="call_llm",
                        details={"provider": ctx.llm_provider},
                        success=False,
                        error=str(e)
                    )
                    raise
                
                # Step 4: Check if LLM wants to use tools
                if llm_response.tool_calls and tool_executor:
                    tool_results = []
                    
                    for tool_call in llm_response.tool_calls:
                        tool_name = tool_call["tool_name"]
                        tool_input = tool_call["tool_input"]
                        
                        # Execute tool
                        tool_result = await tool_executor.execute_tool(
                            tool_name=tool_name,
                            tool_input=tool_input,
                            execution_id=execution_id,
                            tenant_id=tenant_id,
                        )
                        
                        ctx.record_tool_execution(
                            tool_name=tool_name,
                            tool_input=tool_input,
                            success=tool_result.success,
                            result=tool_result.result,
                            error=tool_result.error,
                            duration_ms=tool_result.execution_time_ms,
                        )
                        
                        tool_results.append({
                            "tool_name": tool_name,
                            "result": tool_result.result if tool_result.success else tool_result.error
                        })
                    
                    # Add tool results to messages
                    tool_results_str = "\n".join([
                        f"Tool {r['tool_name']}: {r['result']}"
                        for r in tool_results
                    ])
                    
                    messages.append(LLMMessage(role="system", content=f"Tool results:\n{tool_results_str}"))
                    
                    # Continue loop to let LLM process tool results
                    continue
                
                else:
                    # No more tools to execute, we have final response
                    final_response = llm_response.content
                    break
            
            # Step 5: Update Memory
            if memory_manager and final_response:
                try:
                    await memory_manager.add_message("assistant", final_response)
                except Exception as exc:
                    logger.log_error("Memory manager update failed", {"error": str(exc)})

            if db is not None and final_response:
                try:
                    await self.memory_service.store_memory(
                        db=db,
                        tenant_id=tenant_id,
                        agent_id=agent_id,
                        execution_id=execution_id,
                        role="user",
                        content=user_input,
                    )
                    await self.memory_service.store_memory(
                        db=db,
                        tenant_id=tenant_id,
                        agent_id=agent_id,
                        execution_id=execution_id,
                        role="assistant",
                        content=final_response,
                    )
                    db.flush()
                except Exception as exc:
                    logger.log_error("Long-term memory update failed", {"error": str(exc)})
            
            ctx.record_step(
                action="update_memory",
                details={"saved_response": bool(final_response)}
            )
            
            # Step 6: Complete
            ctx.status = "completed"
            ctx.final_response = final_response or ""
            
            ctx.record_step(
                action="complete",
                details={
                    "response_length": len(final_response or ""),
                    "tools_executed_count": len(ctx.tools_executed),
                    "total_duration_ms": ctx.get_execution_time_ms()
                }
            )
            
            logger.log_execution(
                "Agent execution completed successfully",
                {
                    "execution_id": execution_id,
                    "agent_id": agent_id,
                    "duration_ms": ctx.get_execution_time_ms(),
                    "tools_executed": len(ctx.tools_executed)
                }
            )
            
            return {
                "success": True,
                "response": final_response or "No response generated",
                "execution_context": ctx,
                "error": None
            }
        
        except Exception as e:
            ctx.status = "failed"
            error_msg = str(e)
            
            logger.log_error(
                f"Agent execution failed: {error_msg}",
                {
                    "execution_id": execution_id,
                    "agent_id": agent_id,
                    "exception": type(e).__name__
                }
            )
            
            return {
                "success": False,
                "response": None,
                "execution_context": ctx,
                "error": error_msg
            }

    async def validate_agent_config(self, config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate agent configuration.
        
        Returns:
            (is_valid: bool, error_message: str or None)
        """
        try:
            # Check required fields
            required = ["name", "system_prompt", "llm_provider", "llm_model"]
            for field in required:
                if field not in config:
                    return False, f"Missing required field: {field}"
            
            # Check LLM provider exists
            provider_name = config["llm_provider"]
            if provider_name not in self.provider_registry.list_providers():
                return False, f"Unknown LLM provider: {provider_name}"
            
            # Check tools exist
            tools = config.get("tools", [])
            exist, missing = ToolRegistry.validate_tools_exist(tools)
            if not exist:
                return False, f"Unknown tools: {missing}"
            
            return True, None
        
        except Exception as e:
            return False, f"Validation error: {str(e)}"

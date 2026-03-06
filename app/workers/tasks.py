"""
Celery worker tasks for executing agents.

This module handles asynchronous agent execution with support for both:
- Phase 1/2: Hardcoded agent configuration from Agent.config
- Phase 3: Dynamic agent configuration from AgentLoader (recommended)
"""

import asyncio
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.queue.queue import celery_app
from app.db.database import SessionLocal
from app.engine import AgentEngine
from app.memory import MemoryManager
from app.tools import ToolRegistry, register_builtin_tools
from app.models.agent import AgentExecution, Agent
from app.models.extended import ExecutionLog, AgentUsage, ExecutionStatus
from app.monitoring.logging import StructuredLogger
from app.monitoring.audit_logger import AuditLogger
from app.core.schema import ensure_execution_log_columns
from app.core.tenant_guard import enforce_tenant_match
from app.agents import load_agent_sync
from app.core.exceptions import ValidationError, ResourceNotFoundError, PermissionDeniedError, ConflictError

logger = StructuredLogger(__name__)

# Register built-in tools once at worker startup
register_builtin_tools(ToolRegistry)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.execute_agent",
    max_retries=3,
    time_limit=600,  # 10 minutes hard limit
)
def execute_agent(
    self,
    execution_id: str,
    agent_id: str,
    tenant_id: str,
    user_id: str,
    input_data: dict,
) -> dict:
    """
    Execute an agent in background (async task).
    
    Supports both agent configuration models:
    - Phase 3 (Recommended): Uses AgentLoader to load dynamic config from database
    - Phase 1/2 (Legacy): Falls back to static Agent.config
    
    Flow:
    1. Start execution
    2. Try Phase 3 (load via AgentLoader)
    3. Fall back to Phase 1/2 if needed
    4. Create memory manager
    5. Execute via AgentEngine
    6. Store results and metrics
    
    Args:
        execution_id: Unique execution ID
        agent_id: Agent ID
        tenant_id: Tenant ID
        user_id: User ID
        input_data: {"message": "user input", ...}
        
    Returns:
        dict with execution results
    """
    db = SessionLocal()
    start_time = time.time()
    
    try:
        # Update execution status to running
        execution = db.query(AgentExecution).filter(
            AgentExecution.id == execution_id
        ).first()
        
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")
        
        execution.status = ExecutionStatus.RUNNING.value
        db.commit()
        
        # Load agent
        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.tenant_id == tenant_id
        ).first()
        
        if not agent:
            raise ValueError(f"Agent {agent_id} not found in tenant {tenant_id}")
        enforce_tenant_match(agent.tenant_id, tenant_id, "agent")
        AuditLogger.log_event(
            db=db,
            action="agent_execution_started",
            tenant_id=tenant_id,
            user_id=user_id,
            metadata={"agent_id": agent_id, "execution_id": execution_id, "mode": "worker"},
        )
        
        # **Phase 3 Integration**: Try to load via AgentLoader (recommended)
        agent_config = None
        try:
            logger.log_execution(
                "Attempting Phase 3 dynamic configuration load",
                {"execution_id": execution_id, "agent_id": agent_id}
            )
            
            # Try Phase 3 AgentLoader first
            agent_config = load_agent_sync(db, agent_id, tenant_id)
            
            if agent_config:
                logger.log_execution(
                    "Phase 3 configuration loaded successfully",
                    {
                        "execution_id": execution_id,
                        "version": agent_config.version_number,
                        "tools_count": len(agent_config.tools)
                    }
                )
        except (ValidationError, ResourceNotFoundError, PermissionDeniedError, ConflictError) as e:
            # Phase 3 not available or config invalid, will fallback to Phase 1/2
            logger.log_execution(
                f"Phase 3 load failed, falling back to Phase 1/2: {str(e)}",
                {"execution_id": execution_id, "agent_id": agent_id}
            )
            agent_config = None
        except Exception as e:
            # Unexpected error, log and continue with fallback
            logger.log_error(
                f"Unexpected error loading Phase 3 config: {str(e)}",
                {"execution_id": execution_id, "agent_id": agent_id}
            )
            agent_config = None
        
        # **Phase 1/2 Fallback**: Create config from Agent model if Phase 3 unavailable
        if not agent_config:
            logger.log_execution(
                "Using Phase 1/2 configuration",
                {"execution_id": execution_id, "agent_id": agent_id}
            )
            
            agent_config = {
                "agent_id": agent.id,
                "system_prompt": agent.config.get("system_prompt", "You are a helpful assistant."),
                "llm_provider": agent.config.get("llm_provider", "openai"),
                "llm_model": agent.config.get("llm_model", "gpt-4-turbo-preview"),
                "temperature": agent.config.get("temperature", 0.7),
                "max_tokens": agent.config.get("max_tokens", 2048),
                "tools": agent.config.get("tools", []),
            }
        
        # Initialize memory manager
        memory_manager = MemoryManager(memory_id=execution_id)
        execution.llm_provider = agent_config.get("llm_provider")
        db.commit()
        
        # Initialize engine
        engine = AgentEngine()
        
        # Run async execution in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                engine.execute(
                    agent_config=agent_config,
                    user_input=input_data.get("message", ""),
                    execution_id=execution_id,
                    agent_id=agent_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    memory_manager=memory_manager,
                    max_tool_loops=5,
                    db=db,
                )
            )
        finally:
            loop.close()
        
        # Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        if result["success"]:
            # Update execution with results
            execution.status = ExecutionStatus.COMPLETED.value
            execution.output_data = {
                "response": result["response"],
                "success": True,
            }
            execution.execution_time_ms = execution_time_ms
            execution.completed_at = datetime.now(timezone.utc)
            
            # Store execution logs from context
            ensure_execution_log_columns(db)
            ctx = result["execution_context"]
            for step in ctx.steps:
                log = ExecutionLog(
                    execution_id=execution_id,
                    step=step.step_number,
                    action=step.action,
                    details={
                        "details": step.details,
                        "duration_ms": step.duration_ms,
                        "success": step.success,
                        "error": step.error,
                    },
                    prompt_tokens=ctx.prompt_tokens if step.action == "call_llm" else 0,
                    completion_tokens=ctx.completion_tokens if step.action == "call_llm" else 0,
                    cost_usd=ctx.total_cost_usd if step.action == "call_llm" else 0.0,
                    llm_provider=agent_config.get("llm_provider"),
                    tokens_used=ctx.prompt_tokens + ctx.completion_tokens,
                    llm_latency_ms=ctx.llm_latency_ms,
                    tool_latency_ms=ctx.tool_latency_ms,
                    total_execution_time_ms=execution_time_ms,
                )
                db.add(log)
            
            # Track usage
            usage = AgentUsage(
                tenant_id=tenant_id,
                agent_id=agent_id,
                execution_id=execution_id,
                input_tokens=ctx.prompt_tokens,
                output_tokens=ctx.completion_tokens,
                total_tokens=ctx.prompt_tokens + ctx.completion_tokens,
                execution_time_ms=execution_time_ms,
                model_used=agent_config.get("llm_model"),
                cost_usd=ctx.total_cost_usd,
            )
            db.add(usage)
            
            logger.log_execution(
                "Agent execution completed",
                {
                    "execution_id": execution_id,
                    "agent_id": agent_id,
                    "duration_ms": execution_time_ms,
                    "tokens_used": ctx.prompt_tokens + ctx.completion_tokens,
                    "tools_called": len(ctx.tools_executed),
                }
            )
            AuditLogger.log_event(
                db=db,
                action="agent_execution_completed",
                tenant_id=tenant_id,
                user_id=user_id,
                metadata={
                    "agent_id": agent_id,
                    "execution_id": execution_id,
                    "duration_ms": execution_time_ms,
                    "tokens_used": ctx.prompt_tokens + ctx.completion_tokens,
                },
            )
            
        else:
            # Handle error
            execution.status = ExecutionStatus.FAILED.value
            execution.error_message = result.get("error", "Unknown error")
            execution.execution_time_ms = execution_time_ms
            execution.completed_at = datetime.now(timezone.utc)
            execution.output_data = {"success": False, "error": result.get("error")}
            
            logger.log_error(
                f"Agent execution failed: {result.get('error')}",
                {
                    "execution_id": execution_id,
                    "agent_id": agent_id,
                    "duration_ms": execution_time_ms,
                }
            )
            AuditLogger.log_event(
                db=db,
                action="agent_execution_failed",
                tenant_id=tenant_id,
                user_id=user_id,
                metadata={"agent_id": agent_id, "execution_id": execution_id, "reason": result.get("error", "unknown")},
            )
        
        db.commit()
        
        return {
            "execution_id": execution_id,
            "status": execution.status,
            "success": result["success"],
            "duration_ms": execution_time_ms,
        }
        
    except Exception as exc:
        error_msg = str(exc)
        logger.log_error(
            f"Task exception in execute_agent: {error_msg}",
            {
                "execution_id": execution_id,
                "retry_count": self.request.retries,
                "exception": type(exc).__name__
            }
        )
        AuditLogger.log_event(
            db=db,
            action="agent_execution_failed",
            tenant_id=tenant_id,
            user_id=user_id,
            metadata={"agent_id": agent_id, "execution_id": execution_id, "reason": error_msg},
        )
        
        # Handle task failure
        try:
            execution = db.query(AgentExecution).filter(
                AgentExecution.id == execution_id
            ).first()
            
            if execution:
                execution.status = ExecutionStatus.FAILED.value
                execution.error_message = error_msg
                execution.execution_time_ms = int((time.time() - start_time) * 1000)
                execution.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            pass
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries
            raise self.retry(exc=exc, countdown=countdown)
        else:
            # Max retries exceeded
            return {
                "execution_id": execution_id,
                "status": "failed",
                "success": False,
                "error": error_msg,
                "duration_ms": int((time.time() - start_time) * 1000),
            }
        
    finally:
        db.close()

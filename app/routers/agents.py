"""
Agent management routes with asynchronous execution.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Dict, Any
from datetime import datetime, timezone

from app.db.database import get_db
from app.models.user import User
from app.models.agent import AgentExecution
from app.models.extended import ExecutionLog, AgentUsage, ExecutionStatus
from app.schemas.agent import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentExecuteRequest,
    AgentExecuteResultResponse,
    AgentExecuteAsyncResponse,
    AgentExecutionHistoryItem,
)
from app.schemas.extended import (
    ExecutionDetailResponse, ExecutionLogResponse, AgentUsageResponse, UsageStatsResponse
)
from app.services.agent_service import AgentService
from app.services.usage_service import UsageService
from app.services.rbac_service import RBACService
from app.core.dependencies import (
    get_current_user, get_current_admin, check_execution_quota, check_agent_creation_quota
)
from app.core.schema import ensure_execution_log_columns
from app.core.tenant_guard import enforce_tenant_match
from app.monitoring.logging import logger
from app.monitoring.audit_logger import AuditLogger
from app.agents import get_agent_loader
from app.engine.agent_engine import AgentEngine
from app.engine.config_converter import agent_config_to_dict, dict_to_agent_config_partial
from app.memory import MemoryManager
from app.queue.queue import celery_app
from app.core.exceptions import ValidationError, ResourceNotFoundError, PermissionDeniedError, ConflictError

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreate,
    current_user: User = Depends(get_current_user),
    _: bool = Depends(check_agent_creation_quota),
    db: Session = Depends(get_db),
) -> AgentResponse:
    """
    Create a new AI agent.
    
    User must be authenticated. Agent is scoped to the user's tenant.
    """
    try:
        agent = AgentService.create_agent(
            db,
            agent_data,
            current_user.tenant_id,
            current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        )
    
    logger.log_execution(
        execution_id="",
        agent_id=agent.id,
        tenant_id=current_user.tenant_id,
        status="created",
        details={"name": agent.name},
    )
    
    return AgentResponse.model_validate(agent)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentResponse:
    """
    Get agent details by ID.
    
    Agent must belong to the user's tenant.
    """
    agent = AgentService.get_agent_by_id(db, agent_id, current_user.tenant_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return AgentResponse.model_validate(agent)


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AgentResponse]:
    """
    List all agents for the current tenant.
    
    Supports pagination with skip and limit parameters.
    """
    agents = AgentService.list_agents(db, current_user.tenant_id, skip, limit)
    return [AgentResponse.model_validate(agent) for agent in agents]


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    agent_data: AgentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentResponse:
    """
    Update an agent.
    
    Only the agent creator or tenant admin can update it.
    """
    agent = AgentService.get_agent_by_id(db, agent_id, current_user.tenant_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    
    # Check permissions
    if agent.created_by != current_user.id and not RBACService.is_admin(db, current_user.id, current_user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this agent",
        )
    
    agent = AgentService.update_agent(db, agent, agent_data)
    return AgentResponse.model_validate(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Delete an agent.
    
    Only the agent creator or tenant admin can delete it.
    """
    agent = AgentService.get_agent_by_id(db, agent_id, current_user.tenant_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    
    # Check permissions
    if agent.created_by != current_user.id and not RBACService.is_admin(db, current_user.id, current_user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this agent",
        )
    
    AgentService.delete_agent(db, agent)


@router.post(
    "/{agent_id}/execute",
    response_model=AgentExecuteResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Agent (Synchronous)",
    description=(
        "Execute an agent immediately and return final output plus runtime metrics. "
        "The agent is always resolved inside the authenticated user's tenant."
    ),
)
async def execute_agent(
    agent_id: str,
    request: AgentExecuteRequest = Body(
        ...,
        examples={
            "basic": {
                "summary": "Simple execution input",
                "value": {"message": "Hello agent"},
            }
        },
    ),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(check_execution_quota),
    db: Session = Depends(get_db),
) -> AgentExecuteResultResponse:
    """
    Execute an agent immediately (synchronous) for testing and validation.

    Flow:
    1) Validate tenant isolation
    2) Load agent config via AgentLoader (Phase 3), fallback to legacy if needed
    3) Execute with AgentEngine
    4) Persist AgentExecution + ExecutionLog
    5) Return structured result
    """
    agent = AgentService.get_agent_by_id(db, agent_id, current_user.tenant_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    enforce_tenant_match(agent.tenant_id, current_user.tenant_id, "agent")
    
    if not agent.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent is not active",
        )

    # Create execution record first for traceability
    execution = AgentExecution(
        agent_id=agent_id,
        input_data={"message": request.message},
        status=ExecutionStatus.PENDING.value,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    AuditLogger.log_event(
        db=db,
        action="agent_execution_started",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        metadata={"agent_id": agent_id, "execution_id": execution.id, "mode": "sync"},
    )

    execution.status = ExecutionStatus.RUNNING.value
    db.commit()

    agent_config: dict[str, Any] | Any
    try:
        loader = get_agent_loader()
        loaded_config = await loader.load_agent(
            db=db,
            agent_id=agent_id,
            tenant_id=current_user.tenant_id,
        )
        agent_config = agent_config_to_dict(loaded_config)
    except (ValidationError, ResourceNotFoundError, PermissionDeniedError, ConflictError):
        # Legacy fallback for Phase 1/2 static agents
        agent_config = {
            "agent_id": agent.id,
            "system_prompt": agent.config.get("system_prompt", "You are a helpful assistant."),
            "llm_provider": agent.config.get("llm_provider", "openai"),
            "llm_model": agent.config.get("llm_model", "gpt-4-turbo-preview"),
            "temperature": agent.config.get("temperature", 0.7),
            "max_tokens": agent.config.get("max_tokens", 2048),
            "tools": agent.config.get("tools", []),
        }
    except Exception as exc:
        execution.status = ExecutionStatus.FAILED.value
        execution.error_message = f"Configuration load failed: {str(exc)}"
        execution.completed_at = datetime.now(timezone.utc)
        db.commit()
        AuditLogger.log_event(
            db=db,
            action="agent_execution_failed",
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            metadata={"agent_id": agent_id, "execution_id": execution.id, "reason": "config_load_failed"},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load agent configuration",
        )

    # Ensure backward-compatible dict contract for runtime
    if not isinstance(agent_config, dict):
        agent_config = agent_config_to_dict(agent_config)
    agent_config = dict_to_agent_config_partial(agent_config)
    execution.llm_provider = agent_config.get("llm_provider")
    db.commit()

    engine = AgentEngine()
    memory_manager = MemoryManager(memory_id=execution.id)
    result = await engine.execute(
        agent_config=agent_config,
        user_input=request.message,
        execution_id=execution.id,
        agent_id=agent_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        memory_manager=memory_manager,
        max_tool_loops=5,
        db=db,
    )

    ctx = result["execution_context"]
    tokens_used = ctx.prompt_tokens + ctx.completion_tokens
    execution_time_ms = ctx.get_execution_time_ms()
    tools_executed = [tool["tool_name"] for tool in ctx.tools_executed]

    # Persist execution logs
    ensure_execution_log_columns(db)
    for step in ctx.steps:
        log = ExecutionLog(
            execution_id=execution.id,
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
            llm_provider=ctx.llm_provider,
            tokens_used=tokens_used,
            llm_latency_ms=ctx.llm_latency_ms,
            tool_latency_ms=ctx.tool_latency_ms,
            total_execution_time_ms=execution_time_ms,
        )
        db.add(log)

    if result["success"]:
        execution.status = ExecutionStatus.COMPLETED.value
        execution.output_data = {
            "response": result["response"],
            "tokens_used": tokens_used,
            "tools_executed": tools_executed,
        }
        execution.execution_time_ms = execution_time_ms
    else:
        execution.status = ExecutionStatus.FAILED.value
        execution.error_message = result.get("error", "Execution failed")
        execution.output_data = {"response": "", "tokens_used": tokens_used, "tools_executed": tools_executed}
        execution.execution_time_ms = execution_time_ms

    execution.completed_at = datetime.now(timezone.utc)
    UsageService.record_usage(
        db=db,
        tenant_id=current_user.tenant_id,
        agent_id=agent_id,
        execution_id=execution.id,
        input_tokens=ctx.prompt_tokens,
        output_tokens=ctx.completion_tokens,
        execution_time_ms=execution_time_ms,
        model=agent_config.get("llm_model", "unknown"),
        cost_usd=ctx.total_cost_usd,
    )
    db.commit()

    if not result["success"]:
        AuditLogger.log_event(
            db=db,
            action="agent_execution_failed",
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            metadata={"agent_id": agent_id, "execution_id": execution.id, "reason": result.get("error", "execution_failed")},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Execution failed"),
        )

    AuditLogger.log_event(
        db=db,
        action="agent_execution_completed",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        metadata={
            "agent_id": agent_id,
            "execution_id": execution.id,
            "tokens_used": tokens_used,
            "tools_executed": tools_executed,
            "execution_time_ms": execution_time_ms,
        },
    )

    return AgentExecuteResultResponse(
        execution_id=execution.id,
        response=result["response"],
        tokens_used=tokens_used,
        execution_time_ms=execution_time_ms,
        tools_executed=tools_executed,
        status=execution.status,
    )


@router.post(
    "/{agent_id}/execute-async",
    response_model=AgentExecuteAsyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Execute Agent (Asynchronous)",
)
async def execute_agent_async(
    agent_id: str,
    request: AgentExecuteRequest,
    current_user: User = Depends(get_current_user),
    _: bool = Depends(check_execution_quota),
    db: Session = Depends(get_db),
) -> AgentExecuteAsyncResponse:
    """Queue agent execution in Celery while preserving tenant isolation."""
    agent = AgentService.get_agent_by_id(db, agent_id, current_user.tenant_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    enforce_tenant_match(agent.tenant_id, current_user.tenant_id, "agent")
    if not agent.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent is not active")

    execution = AgentExecution(
        agent_id=agent_id,
        input_data={"message": request.message},
        status=ExecutionStatus.PENDING.value,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    AuditLogger.log_event(
        db=db,
        action="agent_execution_queued",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        metadata={"agent_id": agent_id, "execution_id": execution.id, "mode": "async"},
    )

    try:
        task = celery_app.send_task(
            "app.tasks.agent_tasks.execute_agent_task",
            args=(agent_id, current_user.id, current_user.tenant_id, request.message, execution.id),
            queue="default",
        )
        execution.output_data = {"task_id": task.id}
        db.commit()
    except Exception as exc:
        execution.status = ExecutionStatus.FAILED.value
        execution.error_message = f"Queueing failed: {str(exc)}"
        execution.completed_at = datetime.now(timezone.utc)
        db.commit()
        AuditLogger.log_event(
            db=db,
            action="agent_execution_failed",
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            metadata={"agent_id": agent_id, "execution_id": execution.id, "reason": "queueing_failed"},
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to queue execution")

    return AgentExecuteAsyncResponse(execution_id=execution.id, status="queued")


@router.get(
    "/{agent_id}/executions",
    response_model=list[AgentExecutionHistoryItem],
    status_code=status.HTTP_200_OK,
    summary="List agent executions",
)
async def list_executions(
    agent_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AgentExecutionHistoryItem]:
    """Return execution history for an agent in the current tenant."""
    agent = AgentService.get_agent_by_id(db, agent_id, current_user.tenant_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    enforce_tenant_match(agent.tenant_id, current_user.tenant_id, "agent")

    rows = (
        db.query(AgentExecution)
        .filter(AgentExecution.agent_id == agent_id)
        .order_by(AgentExecution.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [AgentExecutionHistoryItem.model_validate(row) for row in rows]


@router.get("/{agent_id}/executions/{execution_id}", response_model=ExecutionDetailResponse)
async def get_execution(
    agent_id: str,
    execution_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExecutionDetailResponse:
    """
    Get execution details with logs and status.
    """
    agent = AgentService.get_agent_by_id(db, agent_id, current_user.tenant_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    enforce_tenant_match(agent.tenant_id, current_user.tenant_id, "agent")
    
    execution = db.query(AgentExecution).filter(
        and_(
            AgentExecution.id == execution_id,
            AgentExecution.agent_id == agent_id,
        )
    ).first()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )
    
    # Get execution logs
    logs = db.query(ExecutionLog).filter(
        ExecutionLog.execution_id == execution_id
    ).order_by(ExecutionLog.step).all()
    
    return ExecutionDetailResponse(
        **execution.__dict__,
        logs=[ExecutionLogResponse.model_validate(log) for log in logs],
    )


@router.get("/{agent_id}/usage", response_model=UsageStatsResponse)
async def get_agent_usage(
    agent_id: str,
    days: int = Query(30, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UsageStatsResponse:
    """
    Get usage statistics for an agent.
    """
    agent = AgentService.get_agent_by_id(db, agent_id, current_user.tenant_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    
    stats = UsageService.get_tenant_usage_stats(db, current_user.tenant_id, days)
    return UsageStatsResponse(**stats)


@router.get("/usage/summary", response_model=UsageStatsResponse)
async def get_tenant_usage(
    days: int = Query(30, ge=1, le=90),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> UsageStatsResponse:
    """
    Get total usage statistics for the tenant.
    Only available to admins.
    """
    stats = UsageService.get_tenant_usage_stats(db, current_user.tenant_id, days)
    return UsageStatsResponse(**stats)


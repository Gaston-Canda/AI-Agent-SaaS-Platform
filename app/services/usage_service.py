"""
Service for tracking usage and metrics.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime, timedelta
from typing import Dict, Any, List

from app.models.extended import AgentUsage, TenantSubscription, ExecutionLog, ExecutionStatus
from app.models.agent import AgentExecution, Agent
from app.models.subscription import SubscriptionPlan


class UsageService:
    """Service for tracking and reporting usage."""
    
    @staticmethod
    def record_usage(
        db: Session,
        tenant_id: str,
        agent_id: str,
        execution_id: str,
        input_tokens: int,
        output_tokens: int,
        execution_time_ms: int,
        model: str,
        cost_usd: float = 0.0,
    ) -> AgentUsage:
        """Record usage for an execution."""
        usage = AgentUsage(
            tenant_id=tenant_id,
            agent_id=agent_id,
            execution_id=execution_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            execution_time_ms=execution_time_ms,
            model_used=model,
            cost_usd=cost_usd,
        )
        db.add(usage)
        db.commit()
        db.refresh(usage)
        return usage
    
    @staticmethod
    def get_tenant_usage_stats(
        db: Session,
        tenant_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get usage statistics for a tenant in the last N days."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Query executions
        executions = (
            db.query(AgentExecution)
            .join(Agent, Agent.id == AgentExecution.agent_id)
            .filter(
                and_(
                    Agent.tenant_id == tenant_id,
                    AgentExecution.created_at >= start_date,
                )
            )
            .all()
        )
        
        # Calculate stats
        total = len(executions)
        succeeded = sum(1 for e in executions if str(e.status).lower() == ExecutionStatus.COMPLETED.value)
        failed = sum(1 for e in executions if str(e.status).lower() == ExecutionStatus.FAILED.value)
        
        # Query usage
        usage_records = db.query(AgentUsage).filter(
            and_(
                AgentUsage.tenant_id == tenant_id,
                AgentUsage.created_at >= start_date,
            )
        ).all()
        
        total_tokens = sum(u.total_tokens for u in usage_records)
        total_cost = sum(u.cost_usd for u in usage_records)
        total_execution_time_ms = sum(u.execution_time_ms for u in usage_records)
        
        return {
            "period_start": start_date,
            "period_end": datetime.utcnow(),
            "total_executions": total,
            "successful_executions": succeeded,
            "failed_executions": failed,
            "total_tokens": total_tokens,
            "total_execution_time_ms": total_execution_time_ms,
            "estimated_cost_usd": total_cost,
        }
    
    @staticmethod
    def get_subscription(db: Session, tenant_id: str) -> TenantSubscription:
        """Get subscription for tenant."""
        subscription = db.query(TenantSubscription).filter(
            TenantSubscription.tenant_id == tenant_id,
        ).first()
        
        if not subscription:
            free_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_name == "free").first()
            subscription = TenantSubscription(
                tenant_id=tenant_id,
                plan_name="free",
                status="trialing",
                trial_active=True,
                trial_start=datetime.utcnow(),
                trial_end=datetime.utcnow() + timedelta(days=14),
                current_period_start=datetime.utcnow(),
                current_period_end=datetime.utcnow() + timedelta(days=14),
            )
            if free_plan:
                subscription.plan_id = free_plan.id
                subscription.max_agents = free_plan.max_agents
                subscription.max_executions_month = free_plan.max_executions_month
                subscription.tokens_per_month = free_plan.max_tokens_month
                subscription.max_tool_calls = free_plan.max_tool_calls
                subscription.concurrent_executions = free_plan.concurrent_executions

            db.add(subscription)
            db.commit()
            db.refresh(subscription)
        
        return subscription

    @staticmethod
    def check_agent_quota(
        db: Session,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """Check if tenant can create more agents under current plan."""
        subscription = UsageService.get_subscription(db, tenant_id)
        current_agents = db.query(func.count(Agent.id)).filter(Agent.tenant_id == tenant_id).scalar() or 0
        exceeded = subscription.max_agents > 0 and current_agents >= subscription.max_agents
        return {
            "agents_count": int(current_agents),
            "agents_limit": int(subscription.max_agents or 0),
            "agents_exceeded": bool(exceeded),
            "plan_name": subscription.plan_name,
        }
    
    @staticmethod
    def check_quota(
        db: Session,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """Check if tenant has exceeded quota."""
        subscription = UsageService.get_subscription(db, tenant_id)
        
        # Check daily limit
        today = datetime.utcnow().date()
        today_executions = (
            db.query(func.count(AgentExecution.id))
            .join(Agent, Agent.id == AgentExecution.agent_id)
            .filter(
                and_(
                    Agent.tenant_id == tenant_id,
                    func.date(AgentExecution.created_at) == today,
                )
            )
            .scalar()
            or 0
        )

        daily_exceeded = (
            subscription.executions_per_day > 0
            and today_executions >= subscription.executions_per_day
        )

        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_tokens = (
            db.query(func.coalesce(func.sum(AgentUsage.total_tokens), 0))
            .filter(
                and_(
                    AgentUsage.tenant_id == tenant_id,
                    AgentUsage.created_at >= month_start,
                )
            )
            .scalar()
            or 0
        )
        monthly_tokens_exceeded = (
            subscription.tokens_per_month > 0
            and month_tokens >= subscription.tokens_per_month
        )

        monthly_executions = (
            db.query(func.count(AgentExecution.id))
            .join(Agent, Agent.id == AgentExecution.agent_id)
            .filter(
                and_(
                    Agent.tenant_id == tenant_id,
                    AgentExecution.created_at >= month_start,
                )
            )
            .scalar()
            or 0
        )
        monthly_executions_exceeded = (
            subscription.max_executions_month > 0
            and monthly_executions >= subscription.max_executions_month
        )

        monthly_tool_calls = (
            db.query(func.count(ExecutionLog.id))
            .join(AgentExecution, AgentExecution.id == ExecutionLog.execution_id)
            .join(Agent, Agent.id == AgentExecution.agent_id)
            .filter(
                and_(
                    Agent.tenant_id == tenant_id,
                    ExecutionLog.action == "execute_tool",
                    ExecutionLog.timestamp >= month_start,
                )
            )
            .scalar()
            or 0
        )
        monthly_tool_calls_exceeded = (
            subscription.max_tool_calls > 0
            and monthly_tool_calls >= subscription.max_tool_calls
        )
        
        return {
            "executions_today": today_executions,
            "daily_limit": subscription.executions_per_day,
            "daily_exceeded": daily_exceeded,
            "executions_this_month": int(monthly_executions),
            "monthly_execution_limit": int(subscription.max_executions_month or 0),
            "monthly_executions_exceeded": monthly_executions_exceeded,
            "tokens_this_month": int(month_tokens),
            "monthly_token_limit": subscription.tokens_per_month,
            "monthly_tokens_exceeded": monthly_tokens_exceeded,
            "tool_calls_this_month": int(monthly_tool_calls),
            "monthly_tool_calls_limit": int(subscription.max_tool_calls or 0),
            "monthly_tool_calls_exceeded": monthly_tool_calls_exceeded,
            "max_agents": int(subscription.max_agents or 0),
            "plan_name": subscription.plan_name,
        }

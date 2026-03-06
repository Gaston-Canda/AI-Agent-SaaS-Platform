"""Billing and subscription business logic."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.agent import Agent, AgentExecution
from app.models.extended import AgentUsage, TenantSubscription, ExecutionLog
from app.models.subscription import SubscriptionPlan


DEFAULT_PLANS: list[dict] = [
    {
        "plan_name": "free",
        "price": 0.0,
        "max_agents": 3,
        "max_executions_month": 1000,
        "max_tokens_month": 100_000,
        "max_tool_calls": 500,
        "concurrent_executions": 2,
    },
    {
        "plan_name": "starter",
        "price": 29.0,
        "max_agents": 15,
        "max_executions_month": 10_000,
        "max_tokens_month": 1_000_000,
        "max_tool_calls": 10_000,
        "concurrent_executions": 5,
    },
    {
        "plan_name": "pro",
        "price": 99.0,
        "max_agents": 100,
        "max_executions_month": 100_000,
        "max_tokens_month": 10_000_000,
        "max_tool_calls": 100_000,
        "concurrent_executions": 20,
    },
    {
        "plan_name": "enterprise",
        "price": 499.0,
        "max_agents": 1000,
        "max_executions_month": 1_000_000,
        "max_tokens_month": 200_000_000,
        "max_tool_calls": 1_000_000,
        "concurrent_executions": 100,
    },
]


class BillingService:
    """Service layer for plans/subscriptions and usage summaries."""

    @staticmethod
    def ensure_default_plans(db: Session) -> None:
        existing = {p.plan_name for p in db.query(SubscriptionPlan).all()}
        for item in DEFAULT_PLANS:
            if item["plan_name"] in existing:
                continue
            db.add(
                SubscriptionPlan(
                    id=str(uuid.uuid4()),
                    plan_name=item["plan_name"],
                    price=item["price"],
                    max_agents=item["max_agents"],
                    max_executions_month=item["max_executions_month"],
                    max_tokens_month=item["max_tokens_month"],
                    max_tool_calls=item["max_tool_calls"],
                    concurrent_executions=item["concurrent_executions"],
                    created_at=datetime.utcnow(),
                )
            )
        db.commit()

    @staticmethod
    def list_plans(db: Session) -> list[SubscriptionPlan]:
        BillingService.ensure_default_plans(db)
        return (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.is_active == True)
            .order_by(SubscriptionPlan.price.asc())
            .all()
        )

    @staticmethod
    def _sync_subscription_limits(subscription: TenantSubscription, plan: SubscriptionPlan) -> None:
        subscription.plan_name = plan.plan_name
        subscription.plan_id = plan.id
        subscription.max_agents = plan.max_agents
        subscription.max_executions_month = plan.max_executions_month
        subscription.tokens_per_month = plan.max_tokens_month
        subscription.max_tool_calls = plan.max_tool_calls
        subscription.concurrent_executions = plan.concurrent_executions

    @staticmethod
    def get_or_create_subscription(db: Session, tenant_id: str) -> TenantSubscription:
        BillingService.ensure_default_plans(db)
        subscription = db.query(TenantSubscription).filter(TenantSubscription.tenant_id == tenant_id).first()
        if subscription:
            if subscription.plan_id is None:
                free_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_name == "free").first()
                if free_plan:
                    BillingService._sync_subscription_limits(subscription, free_plan)
                    db.commit()
                    db.refresh(subscription)
            return subscription

        free_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_name == "free").first()
        now = datetime.utcnow()
        trial_end = now + timedelta(days=14)

        subscription = TenantSubscription(
            tenant_id=tenant_id,
            status="trialing",
            trial_start=now,
            trial_end=trial_end,
            trial_active=True,
            current_period_start=now,
            current_period_end=trial_end,
            cancel_at_period_end=False,
        )
        if free_plan:
            BillingService._sync_subscription_limits(subscription, free_plan)

        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        return subscription

    @staticmethod
    def change_plan(db: Session, tenant_id: str, plan_name: str) -> TenantSubscription:
        subscription = BillingService.get_or_create_subscription(db, tenant_id)
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_name == plan_name, SubscriptionPlan.is_active == True).first()
        if not plan:
            raise ValueError("Plan not found")

        BillingService._sync_subscription_limits(subscription, plan)
        subscription.status = "active"
        subscription.trial_active = False
        subscription.current_period_start = datetime.utcnow()
        subscription.current_period_end = datetime.utcnow() + timedelta(days=30)
        db.commit()
        db.refresh(subscription)
        return subscription

    @staticmethod
    def cancel_subscription(db: Session, tenant_id: str) -> TenantSubscription:
        subscription = BillingService.get_or_create_subscription(db, tenant_id)
        subscription.cancel_at_period_end = True
        subscription.status = "cancelling"
        db.commit()
        db.refresh(subscription)
        return subscription

    @staticmethod
    def get_usage_dashboard(db: Session, tenant_id: str) -> dict:
        subscription = BillingService.get_or_create_subscription(db, tenant_id)
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        tokens_used = (
            db.query(AgentUsage)
            .filter(AgentUsage.tenant_id == tenant_id, AgentUsage.created_at >= month_start)
            .with_entities(AgentUsage.total_tokens)
            .all()
        )
        executions_used = (
            db.query(AgentExecution)
            .join(Agent, Agent.id == AgentExecution.agent_id)
            .filter(Agent.tenant_id == tenant_id, AgentExecution.created_at >= month_start)
            .count()
        )
        tool_usage = (
            db.query(ExecutionLog)
            .join(AgentExecution, AgentExecution.id == ExecutionLog.execution_id)
            .join(Agent, Agent.id == AgentExecution.agent_id)
            .filter(Agent.tenant_id == tenant_id, ExecutionLog.action == "execute_tool", ExecutionLog.timestamp >= month_start)
            .count()
        )

        total_tokens = sum(row.total_tokens for row in tokens_used)

        return {
            "plan_name": subscription.plan_name,
            "status": subscription.status,
            "trial_active": bool(subscription.trial_active),
            "trial_end": subscription.trial_end,
            "tokens_used": total_tokens,
            "tokens_limit": subscription.tokens_per_month,
            "executions_used": executions_used,
            "executions_limit": subscription.max_executions_month,
            "tools_used": tool_usage,
            "tools_limit": subscription.max_tool_calls,
            "max_agents": subscription.max_agents,
        }

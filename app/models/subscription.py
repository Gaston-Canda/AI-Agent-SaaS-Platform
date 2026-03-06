"""Subscription plan models and compatibility exports."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Index

from app.db.database import Base
from app.models.extended import TenantSubscription


class SubscriptionPlan(Base):
    """Commercial subscription plan with enforceable limits."""

    __tablename__ = "subscription_plans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_name = Column(String(50), nullable=False, unique=True)
    price = Column(Float, nullable=False, default=0.0)
    currency = Column(String(8), nullable=False, default="USD")
    billing_interval = Column(String(20), nullable=False, default="monthly")

    # Product limits
    max_agents = Column(Integer, nullable=False, default=3)
    max_executions_month = Column(Integer, nullable=False, default=1000)
    max_tokens_month = Column(Integer, nullable=False, default=100000)
    max_tool_calls = Column(Integer, nullable=False, default=500)
    concurrent_executions = Column(Integer, nullable=False, default=2)

    # Billing provider metadata
    stripe_price_id = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_subscription_plans_name", "plan_name"),
        Index("idx_subscription_plans_active", "is_active"),
    )


__all__ = ["SubscriptionPlan", "TenantSubscription"]

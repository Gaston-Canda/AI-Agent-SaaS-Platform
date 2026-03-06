"""Pydantic schemas for billing API."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class SubscriptionPlanResponse(BaseModel):
    id: str
    plan_name: str
    price: float
    currency: str
    billing_interval: str
    max_agents: int
    max_executions_month: int
    max_tokens_month: int
    max_tool_calls: int
    concurrent_executions: int


class TenantSubscriptionResponse(BaseModel):
    id: str
    tenant_id: str
    plan_id: str | None = None
    plan_name: str
    status: str
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool
    trial_start: datetime | None = None
    trial_end: datetime | None = None
    trial_active: bool


class CheckoutRequest(BaseModel):
    plan_name: str = Field(..., min_length=2, max_length=50)


class CheckoutResponse(BaseModel):
    session_id: str
    checkout_url: str


class CancelSubscriptionResponse(BaseModel):
    status: str
    cancel_at_period_end: bool


class BillingUsageDashboardResponse(BaseModel):
    plan_name: str
    status: str
    trial_active: bool
    trial_end: datetime | None = None
    tokens_used: int
    tokens_limit: int
    executions_used: int
    executions_limit: int
    tools_used: int
    tools_limit: int
    max_agents: int

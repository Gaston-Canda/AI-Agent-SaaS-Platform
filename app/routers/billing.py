"""Billing routes for plans, subscriptions, checkout, and webhooks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.billing.stripe_service import StripeService
from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.billing import (
    BillingUsageDashboardResponse,
    CancelSubscriptionResponse,
    CheckoutRequest,
    CheckoutResponse,
    SubscriptionPlanResponse,
    TenantSubscriptionResponse,
)
from app.services.billing_service import BillingService


router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/plans", response_model=list[SubscriptionPlanResponse])
async def list_plans(db: Session = Depends(get_db)) -> list[SubscriptionPlanResponse]:
    plans = BillingService.list_plans(db)
    return [SubscriptionPlanResponse.model_validate(plan, from_attributes=True) for plan in plans]


@router.get("/subscription", response_model=TenantSubscriptionResponse)
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenantSubscriptionResponse:
    subscription = BillingService.get_or_create_subscription(db, current_user.tenant_id)
    return TenantSubscriptionResponse.model_validate(subscription, from_attributes=True)


@router.get("/usage", response_model=BillingUsageDashboardResponse)
async def get_billing_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BillingUsageDashboardResponse:
    data = BillingService.get_usage_dashboard(db, current_user.tenant_id)
    return BillingUsageDashboardResponse(**data)


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    payload: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    plans = {p.plan_name: p for p in BillingService.list_plans(db)}
    plan = plans.get(payload.plan_name)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    # Fallback path for local/dev or when Stripe price is not configured.
    if not plan.stripe_price_id:
        updated = BillingService.change_plan(db, current_user.tenant_id, payload.plan_name)
        return CheckoutResponse(session_id=updated.id, checkout_url="")

    try:
        result = StripeService.create_checkout_session(
            tenant_id=current_user.tenant_id,
            tenant_email=current_user.email,
            stripe_price_id=plan.stripe_price_id,
            metadata={"plan_name": payload.plan_name},
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    return CheckoutResponse(session_id=result.session_id, checkout_url=result.checkout_url)


@router.post("/cancel", response_model=CancelSubscriptionResponse)
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CancelSubscriptionResponse:
    subscription = BillingService.get_or_create_subscription(db, current_user.tenant_id)
    if subscription.stripe_subscription_id:
        try:
            StripeService.cancel_subscription(subscription.stripe_subscription_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    updated = BillingService.cancel_subscription(db, current_user.tenant_id)
    return CancelSubscriptionResponse(status=updated.status, cancel_at_period_end=bool(updated.cancel_at_period_end))


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    try:
        event = StripeService.construct_webhook_event(payload, signature)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        tenant_id = (data.get("metadata") or {}).get("tenant_id")
        plan_name = (data.get("metadata") or {}).get("plan_name")
        if tenant_id and plan_name:
            BillingService.change_plan(db, tenant_id, plan_name)

    return {"received": True}

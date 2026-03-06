"""Stripe billing integration helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.monitoring.logging import StructuredLogger


logger = StructuredLogger(__name__)


@dataclass
class StripeCheckoutResult:
    session_id: str
    checkout_url: str


class StripeService:
    """Thin wrapper for Stripe operations with graceful fallbacks."""

    @staticmethod
    def _get_client() -> Any:
        if not settings.STRIPE_API_KEY:
            raise RuntimeError("STRIPE_API_KEY not configured")
        try:
            import stripe  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("stripe package is not installed") from exc

        stripe.api_key = settings.STRIPE_API_KEY
        return stripe

    @classmethod
    def create_checkout_session(
        cls,
        *,
        tenant_id: str,
        tenant_email: str,
        stripe_price_id: str,
        metadata: dict[str, str] | None = None,
    ) -> StripeCheckoutResult:
        stripe = cls._get_client()
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            customer_email=tenant_email,
            line_items=[{"price": stripe_price_id, "quantity": 1}],
            success_url=settings.STRIPE_SUCCESS_URL,
            cancel_url=settings.STRIPE_CANCEL_URL,
            metadata={"tenant_id": tenant_id, **(metadata or {})},
        )
        logger.log_execution("stripe_checkout_created", {"tenant_id": tenant_id, "session_id": session.id})
        return StripeCheckoutResult(session_id=session.id, checkout_url=session.url)

    @classmethod
    def cancel_subscription(cls, stripe_subscription_id: str) -> dict[str, Any]:
        stripe = cls._get_client()
        subscription = stripe.Subscription.modify(
            stripe_subscription_id,
            cancel_at_period_end=True,
        )
        logger.log_execution("stripe_subscription_cancel_requested", {"subscription_id": stripe_subscription_id})
        return {
            "id": subscription.id,
            "status": subscription.status,
            "cancel_at_period_end": bool(subscription.cancel_at_period_end),
        }

    @classmethod
    def construct_webhook_event(cls, payload: bytes, signature: str) -> dict[str, Any]:
        stripe = cls._get_client()
        if not settings.STRIPE_WEBHOOK_SECRET:
            raise RuntimeError("STRIPE_WEBHOOK_SECRET not configured")
        event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
        return event

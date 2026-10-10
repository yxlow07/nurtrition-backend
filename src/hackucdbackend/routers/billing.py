import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
import stripe

from hackucdbackend.core.config import settings
from hackucdbackend.core.security import get_current_user
from hackucdbackend.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["Billing & Stripe Checkout"])

# In-memory subscription state cache for active demo users
USER_SUBSCRIPTIONS: Dict[str, Dict[str, Any]] = {}

PLANS = {
    "monthly": {
        "id": "nurtrition_circle_monthly",
        "name": "Nurtrition Circle Pro (Monthly)",
        "price_cents": 699,
        "price_display": "$6.99",
        "interval": "month",
        "features": [
            "Unlimited AI vision plate audits",
            "Full family table feed & live care reactions (❤️ & 🍵)",
            "Weekly family narrative digests & grocery swaps",
            "Up to 6 family circle member invites",
        ],
    },
    "annual": {
        "id": "nurtrition_circle_annual",
        "name": "Nurtrition Circle Pro (Annual)",
        "price_cents": 5900,
        "price_display": "$59.00",
        "interval": "year",
        "savings": "Save 30%",
        "features": [
            "Everything in Monthly plan",
            "Priority OpenRouter AI reasoning analysis",
            "Semester-long student grocery care tracker",
            "Annual family plant diversity certificate",
        ],
    },
}


class CreateCheckoutSessionRequest(BaseModel):
    plan_id: str = "monthly"  # "monthly" or "annual"
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class CheckoutSessionResponse(BaseModel):
    session_id: str
    checkout_url: str
    is_live: bool
    plan_id: str
    amount_cents: int
    currency: str = "usd"


class SubscriptionStatusResponse(BaseModel):
    user_id: str
    is_subscriber: bool
    tier: str
    plan_id: Optional[str] = None
    expires_at: Optional[str] = None
    customer_id: Optional[str] = None


@router.get("/config", summary="Retrieve public Stripe configuration and care circle plans")
async def get_billing_config():
    return {
        "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        "payment_link": settings.STRIPE_PAYMENT_LINK,
        "is_live_configured": bool(settings.STRIPE_SECRET_KEY or settings.STRIPE_PAYMENT_LINK),
        "plans": PLANS,
    }


@router.get("/status", response_model=SubscriptionStatusResponse, summary="Get current user subscription status")
async def get_subscription_status(current_user: User = Depends(get_current_user)):
    user_id_str = str(current_user.id)
    sub = USER_SUBSCRIPTIONS.get(user_id_str)

    if sub and sub.get("is_active"):
        return SubscriptionStatusResponse(
            user_id=user_id_str,
            is_subscriber=True,
            tier="Nurtrition Circle Pro",
            plan_id=sub.get("plan_id"),
            expires_at=sub.get("expires_at"),
            customer_id=sub.get("customer_id"),
        )

    # Automatically query Stripe API for recent completed checkout sessions
    if settings.STRIPE_SECRET_KEY:
        try:
            client = stripe.StripeClient(settings.STRIPE_SECRET_KEY)
            sessions = client.v1.checkout.sessions.list(params={"limit": 20})
            user_email = (current_user.email or "").strip().lower()

            for s in sessions.data:
                matched = False
                meta = s.metadata.to_dict() if hasattr(s.metadata, "to_dict") else (s.metadata or {})
                if s.client_reference_id and str(s.client_reference_id) == user_id_str:
                    matched = True
                elif meta.get("user_id") == user_id_str:
                    matched = True
                elif s.customer_details and getattr(s.customer_details, "email", None):
                    cust_email = str(s.customer_details.email).strip().lower()
                    if user_email and cust_email == user_email:
                        matched = True

                if matched and s.status == "complete" and s.payment_status in ("paid", "no_payment_required"):
                    plan_id = meta.get("plan_id", "monthly")
                    expires = (datetime.now(timezone.utc) + timedelta(days=365 if plan_id == "annual" else 30)).isoformat()
                    cust_id = getattr(s, "customer", None)
                    USER_SUBSCRIPTIONS[user_id_str] = {
                        "is_active": True,
                        "plan_id": plan_id,
                        "session_id": s.id,
                        "customer_id": cust_id,
                        "activated_at": datetime.now(timezone.utc).isoformat(),
                        "expires_at": expires,
                    }
                    return SubscriptionStatusResponse(
                        user_id=user_id_str,
                        is_subscriber=True,
                        tier="Nurtrition Circle Pro",
                        plan_id=plan_id,
                        expires_at=expires,
                        customer_id=cust_id,
                    )
        except Exception as e:
            logger.warning(f"Error checking Stripe sessions for user {user_id_str}: {e}")

    return SubscriptionStatusResponse(
        user_id=user_id_str,
        is_subscriber=False,
        tier="Family Explorer (Free)",
        plan_id=None,
        expires_at=None,
        customer_id=None,
    )


@router.post(
    "/create-checkout-session",
    response_model=CheckoutSessionResponse,
    summary="Create Stripe Checkout Session for subscription",
)
async def create_checkout_session(
    payload: CreateCheckoutSessionRequest,
    current_user: User = Depends(get_current_user),
):
    plan_key = payload.plan_id.lower()
    if plan_key not in PLANS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan '{payload.plan_id}'. Available plans: {list(PLANS.keys())}",
        )

    plan = PLANS[plan_key]
    user_id_str = str(current_user.id)
    family_id_str = str(current_user.family_id or "")

    success_url = payload.success_url or settings.STRIPE_SUCCESS_URL
    cancel_url = payload.cancel_url or settings.STRIPE_CANCEL_URL

    # If live Stripe secret key is supplied, invoke Stripe API
    if settings.STRIPE_SECRET_KEY:
        try:
            client = stripe.StripeClient(settings.STRIPE_SECRET_KEY)
            session = client.v1.checkout.sessions.create(
                params={
                    "payment_method_types": ["card"],
                    "mode": "subscription",
                    "customer_email": current_user.email,
                    "client_reference_id": user_id_str,
                    "metadata": {
                        "user_id": user_id_str,
                        "family_id": family_id_str,
                        "plan_id": plan_key,
                    },
                    "line_items": [
                        {
                            "price_data": {
                                "currency": "usd",
                                "product_data": {
                                    "name": plan["name"],
                                    "description": "nurtrition care circle sync, unlimited AI vision audits, and weekly digests",
                                    "tax_code": "txcd_10000000",
                                },
                                "unit_amount": plan["price_cents"],
                                "recurring": {
                                    "interval": plan["interval"],
                                },
                            },
                            "quantity": 1,
                        }
                    ],
                    "success_url": f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
                    "cancel_url": cancel_url,
                }
            )
            return CheckoutSessionResponse(
                session_id=session.id,
                checkout_url=session.url,
                is_live=True,
                plan_id=plan_key,
                amount_cents=plan["price_cents"],
            )
        except Exception as e:
            # Fallback to simulation if Stripe network or credentials error occurs
            pass

    # If live Stripe Payment Link is supplied, prioritize it
    if settings.STRIPE_PAYMENT_LINK:
        payment_link = settings.STRIPE_PAYMENT_LINK
        sep = "&" if "?" in payment_link else "?"
        direct_url = f"{payment_link}{sep}client_reference_id={user_id_str}"
        if current_user.email:
            direct_url += f"&prefilled_email={current_user.email}"
        return CheckoutSessionResponse(
            session_id=f"pl_{uuid.uuid4().hex[:12]}",
            checkout_url=direct_url,
            is_live=True,
            plan_id=plan_key,
            amount_cents=plan["price_cents"],
        )

    # Local development & offline demonstration mode
    simulated_session_id = f"cs_test_nurtrition_{uuid.uuid4().hex[:12]}"
    simulated_url = f"{settings.APP_URL}/api/v1/billing/mock-checkout?session_id={simulated_session_id}&plan={plan_key}&user={user_id_str}"

    return CheckoutSessionResponse(
        session_id=simulated_session_id,
        checkout_url=simulated_url,
        is_live=False,
        plan_id=plan_key,
        amount_cents=plan["price_cents"],
    )


@router.post("/confirm-payment", summary="Confirm checkout completion and activate membership")
async def confirm_payment(
    session_id: str,
    plan_id: str = "monthly",
    current_user: User = Depends(get_current_user),
):
    user_id_str = str(current_user.id)
    plan = PLANS.get(plan_id, PLANS["monthly"])
    days = 365 if plan["interval"] == "year" else 30
    expires = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

    USER_SUBSCRIPTIONS[user_id_str] = {
        "is_active": True,
        "plan_id": plan_id,
        "session_id": session_id,
        "customer_id": f"cus_demo_{uuid.uuid4().hex[:8]}",
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires,
    }

    return {
        "ok": True,
        "message": f"Successfully upgraded to {plan['name']}!",
        "tier": "Nurtrition Circle Pro",
        "expires_at": expires,
    }


@router.post("/cancel-subscription", summary="Cancel membership and revert to free tier")
async def cancel_subscription(current_user: User = Depends(get_current_user)):
    user_id_str = str(current_user.id)
    if user_id_str in USER_SUBSCRIPTIONS:
        USER_SUBSCRIPTIONS[user_id_str]["is_active"] = False

    return {
        "ok": True,
        "message": "Subscription cancelled. Reverted to free tier.",
        "tier": "Family Explorer (Free)",
    }


@router.post("/webhook", summary="Stripe Webhook Event Listener")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    event = None
    if settings.STRIPE_WEBHOOK_SECRET and sig_header:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")
    else:
        # Fallback to direct json parsing
        try:
            import json
            event = json.loads(payload.decode("utf-8"))
        except Exception:
            return {"status": "ignored"}

    event_type = event.get("type", "") if isinstance(event, dict) else event.type

    if event_type == "checkout.session.completed":
        session = event.get("data", {}).get("object", {}) if isinstance(event, dict) else event.data.object
        user_id = session.get("client_reference_id") or session.get("metadata", {}).get("user_id")
        plan_id = session.get("metadata", {}).get("plan_id", "monthly")
        if user_id:
            USER_SUBSCRIPTIONS[str(user_id)] = {
                "is_active": True,
                "plan_id": plan_id,
                "session_id": session.get("id"),
                "customer_id": session.get("customer"),
                "activated_at": datetime.now(timezone.utc).isoformat(),
            }

    return {"status": "received"}

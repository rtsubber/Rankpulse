"""
BoostRank — Stripe Integration
Subscription management: Free → Pro → Agency upgrade flow.
"""

import os
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.database import get_db, TIER_LIMITS

router = APIRouter(prefix="/api/billing", tags=["billing"])

# Stripe configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Plan IDs — configure these in Stripe Dashboard
STRIPE_PLANS = {
    "pro": {
        "price_id": os.getenv("STRIPE_PRO_PRICE_ID", "price_1TWjY7H5RfM228JPfMtkELFS"),
        "name": "BoostRank Pro",
        "amount": 1900,  # $19/mo
        "features": [
            "50 SEO audits per month",
            "2 competitor comparisons per week",
            "1 PDF report per week",
            "Email support",
        ],
    },
    "business": {
        "price_id": os.getenv("STRIPE_BUSINESS_PRICE_ID", "price_1TWjY8H5RfM228JPjomVzlPr"),
        "name": "BoostRank Business",
        "amount": 4900,  # $49/mo
        "features": [
            "Unlimited SEO audits",
            "10 competitor comparisons per week",
            "Unlimited PDF reports",
            "API access (1,000 calls/month)",
            "Priority support",
        ],
    },
    "agency": {
        "price_id": os.getenv("STRIPE_AGENCY_PRICE_ID", "price_1TWjY8H5RfM228JP4dCwfxKw"),
        "name": "BoostRank Agency",
        "amount": 9900,  # $99/mo
        "features": [
            "Unlimited SEO audits",
            "Unlimited competitor comparisons",
            "Unlimited PDF reports",
            "White-label reports",
            "API access (10,000 calls/month)",
            "Priority support",
        ],
    },
}


class CheckoutRequest(BaseModel):
    plan: str  # "pro" or "agency"
    success_url: str = "https://boostrank.co/dashboard?upgraded=true"
    cancel_url: str = "https://boostrank.co/pricing"


class PortalRequest(BaseModel):
    return_url: str = "https://boostrank.co/dashboard"


@router.get("/plans")
async def get_plans():
    """Get available plans and pricing."""
    plans = {}
    for tier, info in STRIPE_PLANS.items():
        plans[tier] = {
            "name": info["name"],
            "price": f"${info['amount'] / 100:.0f}/month",
            "features": info["features"],
            "limits": TIER_LIMITS[tier],
        }

    plans["free"] = {
        "name": "BoostRank Free",
        "price": "$0/month",
        "features": [
            "5 SEO audits per month",
            "No competitor comparison",
            "No PDF reports",
        ],
        "limits": TIER_LIMITS["free"],
    }

    return {"plans": plans}


@router.post("/checkout")
async def create_checkout_session(
    request: CheckoutRequest,
    user: dict = Depends(lambda: ...),  # Will inject from auth
):
    """Create a Stripe Checkout session for upgrading."""
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
    except ImportError:
        raise HTTPException(status_code=500, detail="Stripe SDK not installed")

    if request.plan not in STRIPE_PLANS:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {request.plan}")

    plan = STRIPE_PLANS[request.plan]

    # Get user from auth dependency
    from app.auth import get_current_user, Security, HTTPAuthorizationCredentials
    # This will be handled by the route in main.py which injects the user

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{
                "price": plan["price_id"],
                "quantity": 1,
            }],
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            metadata={"user_id": str(user.get("id", "")), "plan": request.plan},
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/portal")
async def create_portal_session(request: PortalRequest):
    """Create a Stripe Customer Portal session for managing subscriptions."""
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
    except ImportError:
        raise HTTPException(status_code=500, detail="Stripe SDK not installed")

    # Get user's Stripe customer ID
    from app.auth import get_current_user
    # user = Depends(get_current_user) — handled in main.py

    # This endpoint needs the user injected
    # For now, accept customer_id in request
    customer_id = request.dict().get("customer_id")

    if not customer_id:
        raise HTTPException(status_code=400, detail="Customer ID required")

    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=request.return_url,
        )
        return {"portal_url": session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    body = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY

        event = stripe.Webhook.construct_event(
            body, sig, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {str(e)}")

    event_type = event["type"]

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("metadata", {}).get("user_id")
        plan = session.get("metadata", {}).get("plan")

        if user_id and plan:
            conn = get_db()
            try:
                conn.execute(
                    "UPDATE users SET tier = ?, stripe_customer_id = ? WHERE id = ?",
                    (plan, session.get("customer"), int(user_id)),
                )
                conn.commit()
            finally:
                conn.close()

    elif event_type == "customer.subscription.updated":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")

        # Map Stripe price to tier
        price_id = subscription["items"]["data"][0]["price"]["id"] if subscription["items"]["data"] else None
        tier = "free"
        for plan_name, plan_info in STRIPE_PLANS.items():
            if plan_info["price_id"] == price_id:
                tier = plan_name
                break

        conn = get_db()
        try:
            conn.execute(
                "UPDATE users SET tier = ? WHERE stripe_customer_id = ?",
                (tier, customer_id),
            )
            conn.commit()
        finally:
            conn.close()

    elif event_type == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")

        conn = get_db()
        try:
            conn.execute(
                "UPDATE users SET tier = 'free' WHERE stripe_customer_id = ?",
                (customer_id,),
            )
            conn.commit()
        finally:
            conn.close()

    return {"received": True}
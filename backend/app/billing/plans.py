"""Subscription plan definitions.

Kept as a plain module so quota tuning is a code change (fast, reviewable,
diffable), not a database migration. If plan structure ever grows to need
runtime editing (e.g. per-customer overrides for enterprise deals), that's
a table — but that's a later problem.

Real Stripe integration is not wired here. The org's `plan` field is set
manually by the super admin for now; wiring it to Stripe webhooks would
mostly be a matter of subscribing to `customer.subscription.updated` and
mapping Stripe product IDs to BillingPlan values.
"""

from dataclasses import dataclass

from app.models.enums import BillingPlan


@dataclass(frozen=True)
class PlanDetails:
    """Everything a plan needs to answer 'what does this org get?'"""
    key: BillingPlan
    display_name: str
    monthly_message_quota: int
    price_usd_monthly: int  # 0 for free / enterprise (custom quote)
    max_orgs: int | None = None  # not enforced yet; here for future
    features: tuple[str, ...] = ()


# Order matters: this is what the pricing table renders. Free first, enterprise last.
PLANS: dict[BillingPlan, PlanDetails] = {
    BillingPlan.free: PlanDetails(
        key=BillingPlan.free,
        display_name="Free",
        monthly_message_quota=500,
        price_usd_monthly=0,
        features=(
            "Web chat receptionist",
            "Knowledge base (up to 100 chunks)",
            "Single organization",
            "Community support",
        ),
    ),
    BillingPlan.starter: PlanDetails(
        key=BillingPlan.starter,
        display_name="Starter",
        monthly_message_quota=5_000,
        price_usd_monthly=29,
        features=(
            "Everything in Free",
            "WhatsApp channel",
            "Google Calendar booking",
            "Email support",
            "Audit log CSV export",
        ),
    ),
    BillingPlan.pro: PlanDetails(
        key=BillingPlan.pro,
        display_name="Pro",
        monthly_message_quota=25_000,
        price_usd_monthly=99,
        features=(
            "Everything in Starter",
            "Voice channel (Retell)",
            "Multi-staff seats",
            "Priority support",
            "Advanced analytics",
        ),
    ),
    BillingPlan.enterprise: PlanDetails(
        key=BillingPlan.enterprise,
        display_name="Enterprise",
        monthly_message_quota=1_000_000,
        price_usd_monthly=0,  # "contact us" pricing
        features=(
            "Everything in Pro",
            "Custom quotas",
            "Dedicated success manager",
            "SLA + uptime guarantee",
            "SSO / SAML",
        ),
    ),
}


def get_plan(plan: BillingPlan) -> PlanDetails:
    """Never raises — an unknown/legacy plan value falls back to `free`
    so quota enforcement stays strict but never brings the app down."""
    return PLANS.get(plan, PLANS[BillingPlan.free])


def monthly_message_quota_for(plan: BillingPlan) -> int:
    return get_plan(plan).monthly_message_quota

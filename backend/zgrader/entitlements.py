"""What a given account is allowed to do.

One place for the question "can this user run another check?", so that when
paid plans arrive the answer changes here and nowhere else.

Nothing enforces a limit yet: the Services page describes one for the free
tier, but the number depends on pricing that isn't settled, and shipping a
cap before then would break existing users for no benefit. `FREE_TIER_LIMIT`
is None on purpose -- set it, and the check below starts biting.
"""

from sqlalchemy.orm import Session

from zgrader.models import Submission, User
from zgrader.models.subscription import Subscription, SubscriptionStatus

# None = unlimited. Set an integer to start enforcing the free-tier cap.
FREE_TIER_LIMIT: int | None = None

_ENTITLED_STATUSES = (SubscriptionStatus.active, SubscriptionStatus.trialing)


def has_active_subscription(db: Session, user: User) -> bool:
    return (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user.id,
            Subscription.status.in_(_ENTITLED_STATUSES),
        )
        .first()
        is not None
    )


def submissions_remaining(db: Session, user: User) -> int | None:
    """How many more checks this account can run, or None for unlimited."""
    if FREE_TIER_LIMIT is None or has_active_subscription(db, user):
        return None
    used = db.query(Submission).filter(Submission.user_id == user.id).count()
    return max(0, FREE_TIER_LIMIT - used)


def can_create_submission(db: Session, user: User) -> bool:
    remaining = submissions_remaining(db, user)
    return remaining is None or remaining > 0

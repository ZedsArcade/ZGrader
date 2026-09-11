# Stripe Subscriptions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sell the monthly and annual plans through Stripe Checkout, with founder pricing, a verified idempotent webhook, reconciliation, and the maintenance-Worker bypass — closing remediation items L2 and L3.

**Architecture:** Stripe is the authority on payment; `subscriptions` is a local mirror written by exactly one function, `billing.apply_subscription`, called from the webhook, the reconcile sweep and the admin button. Prices stay in `plan_entitlements`/`Settings` and are sent inline at checkout. Quota windows reset by derivation when the entitled plan changes.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Postgres 16, `stripe` Python SDK, pytest; Next.js 16 App Router, HeroUI v3, TypeScript.

**Spec:** `docs/superpowers/specs/2026-09-11-stripe-subscriptions-design.md` — read it before starting. Section numbers below (§6.2 etc.) refer to it.

## Global Constraints

- **Run pytest from Git Bash**, from `backend/`: `export PATH="$PATH:/c/msys64/mingw64/bin"; export WEASYPRINT_DLL_DIRECTORIES='C:\msys64\mingw64\bin'; ./.venv/Scripts/python.exe -m pytest …`. Never bare `python`.
- **Only `zgrader_test`.** `127.0.0.1:5432` is an SSH tunnel to production. One pytest process at a time.
- **Never pipe pytest through `tail`/`head`.** Redirect to a file and read it.
- **Every assertion is mutation-checked:** after a test passes, revert the line of production code it protects, watch it fail, restore. Record which line in the commit message body.
- **Never add a second rate limiter** — extend `api/ratelimit.py` (`rate_limit`, `user_rate_limit`, or the failure-counting pattern `login_rate_limit` uses).
- **Every `config.py` setting reaches `docker-compose.yml`** (`tests/test_compose_env_coverage.py`).
- **Audit `detail` never carries an email address.**
- **No figure in the site copy.** Prices, seats and allowances come from `/catalog/pricing`; copy carries `{price}`/`{seats}` placeholders.
- **Published promises change with the software.** Terms, Refund Policy and Privacy change in the same PR as the checkout, in English *and* Spanish.
- **Only `zgrader/billing_stripe.py` imports `stripe`.** Tests replace its functions; nothing else is mocked.
- **Money is whole pence, GBP.**
- **Relock after touching dependencies:** `./.venv/Scripts/python.exe -m uv pip compile pyproject.toml --python-platform linux --python-version 3.11 --generate-hashes -o requirements.lock` (from `backend/`).
- **Frontend checks:** `cd frontend && npx tsc --noEmit && npx next build`. Read Spanish back rendered in the browser. No horizontal scroll and no target under 24px at 320/375/768/1024/1280, both languages, signed in and out (`frontend/AGENTS.md`).
- **Branch:** work on `stripe-subscriptions-design` (already holds the spec); rename to `stripe-subscriptions` before opening the PR if preferred.

## Deliberate divergences from the spec

Found while planning; each is small and each is repeated in the task that makes it.

1. `checkout_attempts` gains `stripe_session_url` (Text, nullable), so a second checkout request can hand back the open session's URL without a Stripe call (§6.1 "two tabs").
2. Session `expires_at` is **now + 31 min** (a whole minute clear of Stripe's 30-minute floor, so clock skew cannot reject it), and the hold's `expires_at` is **now + 33 min**, preserving the spec's rule that a hold outlives its session.
3. The one-live-subscription index and the checkout 409 use **`LIVE_STATUSES` = active, trialing, past_due** — including `past_due` *beyond* grace. Otherwise a lapsed-but-not-yet-cancelled subscriber could start a second subscription that the index would then reject inside the webhook. Such a user is sent to the Portal to fix their card instead.
4. `/catalog/pricing` also publishes `terms_version`, which the confirm dialog must echo back to `/billing/checkout`.
5. A signed-out visitor's **Subscribe** goes to `/login` with no return path: the login page has no `?next=` today and adding one safely (open-redirect handling across password and Google flows) is its own change.
6. Subscriptions created in the Stripe Dashboard by hand carry no `metadata.user_id`, so `apply_subscription` ignores them (logged). Sell through the site; fulfil exceptions with `PATCH /admin/users/{id}/quota` as today.

## File map

| File | Responsibility |
|---|---|
| `backend/zgrader/billing_stripe.py` (new) | The only `stripe` import. Plain-dict adapter functions. |
| `backend/zgrader/billing.py` (new) | Checkout, founder seats, `apply_subscription`, `handle_event`, `reconcile`, `current_subscription`, portal URL. |
| `backend/zgrader/models/checkout_attempt.py` (new) | `CheckoutAttempt` + state constants. |
| `backend/zgrader/models/stripe_event.py` (new) | `StripeEvent` idempotency ledger. |
| `backend/zgrader/models/subscription.py` | Status as string, new columns, `LIVE_STATUSES`, partial unique index. |
| `backend/zgrader/models/user.py`, `plan_entitlement.py`, `__init__.py` | `quota_plan`, `stripe_product_id`, registry. |
| `backend/alembic/versions/9e3b5d1f7a24_stripe_billing.py` (new) | The one migration. |
| `backend/zgrader/entitlements.py` | Bounded `past_due` grace; plan-change window reset. |
| `backend/zgrader/schemas/billing.py` (new) | Request/response models. |
| `backend/zgrader/api/routers/billing.py` (new) | `/billing/checkout`, `/portal`, `/subscription`, `/webhook`. |
| `backend/zgrader/api/ratelimit.py` | `stripe_webhook_rate_limit` + `note_failed_webhook`. |
| `backend/zgrader/api/routers/admin.py`, `schemas/admin.py` | `POST /admin/billing/reconcile`; billing fields on `UserQuotaOut`. |
| `backend/zgrader/api/routers/catalog.py`, `schemas/catalog.py` | `billing_enabled`, `founder_seats_remaining`, `terms_version`. |
| `backend/zgrader/api/routers/auth.py` | Stripe-first account deletion; terms version bump. |
| `backend/zgrader/worker/main.py` | Daily `_reconcile_billing`. |
| `backend/zgrader/config.py`, `docker-compose.yml`, `.env.example`, `pyproject.toml`, `requirements.lock` | Keys and dependency. |
| `infra/cloudflare/maintenance-worker.js` | Webhook bypass. |
| `frontend/lib/api.ts`, `frontend/lib/use-pricing.ts` | Billing calls and types; shared plan-name hook. |
| `frontend/components/SubscribeDialog.tsx`, `SubscribeButton.tsx`, `BillingCard.tsx` (new) | Checkout confirm; account billing card. |
| `frontend/app/pricing/pricing-client.tsx`, `app/account/page.tsx`, `app/admin/settings/page.tsx`, `app/refunds/refunds-client.tsx` | Wiring. |
| `frontend/lib/i18n/en.ts`, `es.ts` | Copy and legal pages. |
| `AGENTS.md`, `docs/deployment.md` | Invariants; go-live checklist. |
| Tests (new): `test_billing_config.py`, `test_billing_schema.py`, `test_entitlements_billing.py`, `billing_fakes.py`, `test_billing_apply.py`, `test_billing_checkout.py`, `test_billing_webhook.py`, `test_maintenance_worker_bypass.py`, `test_billing_portal.py`, `test_billing_reconcile.py`, `test_billing_account_deletion.py`, `test_billing_catalog_admin.py` | |

---

### Task 1: Stripe dependency, configuration and the adapter

**Files:**
- Modify: `backend/pyproject.toml`, `backend/requirements.lock`, `backend/zgrader/config.py`, `docker-compose.yml`, `.env.example`
- Create: `backend/zgrader/billing_stripe.py`, `backend/tests/test_billing_config.py`

**Interfaces:**
- Produces: `config.stripe_secret_key: str | None`, `config.stripe_webhook_secret: str | None`, `config.billing_enabled: bool`.
- Produces (`zgrader.billing_stripe`): `STRIPE_API_VERSION: str`; `create_customer(*, user_id: str, email: str) -> dict`; `create_product(*, plan: str, name: str) -> dict`; `create_checkout_session(**params) -> dict`; `create_portal_session(*, customer: str, return_url: str) -> dict`; `retrieve_subscription(subscription_id: str) -> dict | None`; `list_subscriptions() -> Iterator[dict]`; `delete_customer(customer_id: str) -> None`; `cancel_and_refund(subscription_id: str) -> dict`; `construct_event(payload: bytes, sig_header: str) -> dict` (raises `ValueError`).

- [ ] **Step 1: Write the failing config tests**

`backend/tests/test_billing_config.py`:

```python
"""Billing is off until both Stripe keys exist, and says so when a test key
reaches production."""

import logging

from zgrader.config import ZGraderConfig

_SAFE = {
    "secret_key": "s" * 40,
    "database_url": "postgresql+psycopg://real:realpw@db:5432/zgrader",
}


def test_billing_needs_both_keys():
    assert not ZGraderConfig(**_SAFE).billing_enabled
    assert not ZGraderConfig(**_SAFE, stripe_secret_key="sk_test_1").billing_enabled
    assert not ZGraderConfig(**_SAFE, stripe_webhook_secret="whsec_1").billing_enabled
    assert ZGraderConfig(
        **_SAFE, stripe_secret_key="sk_test_1", stripe_webhook_secret="whsec_1"
    ).billing_enabled


def test_a_test_mode_key_in_production_warns_but_boots(caplog):
    with caplog.at_level(logging.WARNING):
        cfg = ZGraderConfig(
            **_SAFE,
            env="production",
            smtp_host="smtp.example.com",
            stripe_secret_key="sk_test_abc",
            stripe_webhook_secret="whsec_abc",
        )
    assert cfg.billing_enabled
    assert any("test-mode" in r.getMessage() for r in caplog.records)


def test_a_live_key_in_production_is_quiet(caplog):
    with caplog.at_level(logging.WARNING):
        ZGraderConfig(
            **_SAFE,
            env="production",
            smtp_host="smtp.example.com",
            stripe_secret_key="sk_live_abc",
            stripe_webhook_secret="whsec_abc",
        )
    assert not any("test-mode" in r.getMessage() for r in caplog.records)
```

- [ ] **Step 2: Run it — expect failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_config.py -v > /tmp/t1.txt 2>&1; echo $?; cat /tmp/t1.txt`
Expected: FAIL — `ZGraderConfig` has no field `stripe_secret_key` / no attribute `billing_enabled`.

- [ ] **Step 3: Add the settings**

In `backend/zgrader/config.py`, directly after the `google_enabled` property:

```python
    # Stripe billing. Off unless both are set, exactly like Google sign-in: a
    # deployment with no Stripe account keeps "Get in touch" on /pricing
    # rather than offering a checkout that cannot work, and every /billing
    # route answers 404. The webhook secret is the endpoint's signing secret
    # (whsec_...), not the API key -- the two come from different pages of the
    # Stripe Dashboard and swapping them fails every signature check.
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None

    @property
    def billing_enabled(self) -> bool:
        return bool(self.stripe_secret_key and self.stripe_webhook_secret)
```

And a validator after `_warn_about_unusable_smtp`:

```python
    @model_validator(mode="after")
    def _warn_about_test_mode_stripe(self) -> "ZGraderConfig":
        """A test key in production is allowed -- it is how a trial run
        works -- but it must never be a surprise: every checkout would take
        test cards and no money would move."""
        if self.env == "production" and (self.stripe_secret_key or "").startswith("sk_test_"):
            logger.warning(
                "ZGRADER_STRIPE_SECRET_KEY is a test-mode key in production: checkouts "
                "accept test cards and no real payment is taken."
            )
        return self
```

- [ ] **Step 4: Run the config tests — expect PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_config.py -v > /tmp/t1.txt 2>&1; echo $?`
Expected: `0`.

- [ ] **Step 5: Expose the keys through compose**

In `docker-compose.yml`, inside the `&backend-env` block (it is shared by backend and worker via `*backend-env`; reconcile runs in the worker, so both need it), after the `ZGRADER_GOOGLE_CLIENT_SECRET` line:

```yaml
      # Stripe billing. Both empty = billing off (config.billing_enabled).
      # See docs/deployment.md "Taking payments" before setting either.
      ZGRADER_STRIPE_SECRET_KEY: ${ZGRADER_STRIPE_SECRET_KEY:-}
      ZGRADER_STRIPE_WEBHOOK_SECRET: ${ZGRADER_STRIPE_WEBHOOK_SECRET:-}
```

In `.env.example`, after the Google entries:

```bash
# Stripe billing -- leave both empty until docs/deployment.md "Taking payments"
# is done. The webhook secret is the endpoint's signing secret (whsec_...).
ZGRADER_STRIPE_SECRET_KEY=
ZGRADER_STRIPE_WEBHOOK_SECRET=
```

Run: `./.venv/Scripts/python.exe -m pytest tests/test_compose_env_coverage.py -v > /tmp/t1.txt 2>&1; echo $?`
Expected: `0`. (Remove the compose lines and it names both settings — that is the mutation check.)

- [ ] **Step 6: Add the dependency and relock**

In `backend/pyproject.toml` `dependencies`, after `httpx`:

```toml
    # Billing (zgrader.billing_stripe is the only importer). Checkout and the
    # Customer Portal are Stripe-hosted, so no card data reaches this server.
    "stripe>=12",
```

Then, from `backend/`:

```bash
./.venv/Scripts/python.exe -m pip install "stripe>=12"
./.venv/Scripts/python.exe -m uv pip compile pyproject.toml --python-platform linux --python-version 3.11 --generate-hashes -o requirements.lock
./.venv/Scripts/python.exe -c "import stripe; print(stripe.VERSION, stripe.api_version)"
```

Note the printed API version string; Step 7 records it. Run `./.venv/Scripts/python.exe -m pytest tests/test_lockfile_covers_dependencies.py -v > /tmp/t1.txt 2>&1; echo $?` → `0`.

- [ ] **Step 7: Write the adapter**

`backend/zgrader/billing_stripe.py`:

```python
"""The only module that talks to Stripe.

Everything billing does to Stripe goes through a function here, for two
reasons. Tests replace these functions and nothing else, so no test needs the
network and no test mocks the SDK's internals. And the SDK's shape moves
between API versions -- recent ones moved the billing-period dates off the
subscription onto its items, and payments off the invoice -- so there is one
file to read when it moves again.

Every function returns plain dicts. How dict-like the SDK's StripeObject is
has changed across major versions; converting at the boundary means the rest
of the code indexes dicts and never has to care.
"""

import json
from collections.abc import Iterator

import stripe

from zgrader.config import config

#: The API version the SDK pins, recorded when this code was written against
#: it. The SDK sends its own pinned version with every request, so upgrading
#: the `stripe` package silently changes the shape of every object this file
#: returns. tests/test_billing_config.py fails when the two differ -- that is a
#: prompt to re-read this module against the new version, not to bump the
#: constant blindly.
STRIPE_API_VERSION = "PASTE THE VALUE PRINTED IN STEP 6"

#: Seconds per Stripe request. The worker's reconcile shares a loop with scan
#: analysis, so a hung call must not stall it for the SDK's default 80s.
_TIMEOUT_SECONDS = 20

_configured = False


def _ready() -> None:
    global _configured
    if not config.billing_enabled:
        raise RuntimeError("Stripe is not configured on this deployment")
    if not _configured:
        stripe.api_key = config.stripe_secret_key
        stripe.max_network_retries = 2
        stripe.default_http_client = stripe.new_default_http_client(timeout=_TIMEOUT_SECONDS)
        _configured = True


def _plain(obj) -> dict:
    # StripeObject.__str__ is its JSON form in every SDK generation, which
    # makes this the one conversion that does not depend on the version.
    return json.loads(str(obj))


def _missing(exc: stripe.InvalidRequestError) -> bool:
    return getattr(exc, "code", None) == "resource_missing"


def create_customer(*, user_id: str, email: str) -> dict:
    _ready()
    # Idempotency key per user: a double-clicked Subscribe cannot create two
    # customers, because Stripe answers the second call with the first result.
    return _plain(
        stripe.Customer.create(
            email=email, metadata={"user_id": user_id}, idempotency_key=f"customer-{user_id}"
        )
    )


def create_product(*, plan: str, name: str) -> dict:
    _ready()
    return _plain(
        stripe.Product.create(
            name=name, metadata={"plan": plan}, idempotency_key=f"product-{plan}"
        )
    )


def create_checkout_session(**params) -> dict:
    _ready()
    return _plain(stripe.checkout.Session.create(**params))


def create_portal_session(*, customer: str, return_url: str) -> dict:
    _ready()
    return _plain(stripe.billing_portal.Session.create(customer=customer, return_url=return_url))


def retrieve_subscription(subscription_id: str) -> dict | None:
    _ready()
    try:
        return _plain(stripe.Subscription.retrieve(subscription_id))
    except stripe.InvalidRequestError as exc:
        if _missing(exc):
            return None
        raise


def list_subscriptions() -> Iterator[dict]:
    _ready()
    for sub in stripe.Subscription.list(status="all", limit=100).auto_paging_iter():
        yield _plain(sub)


def delete_customer(customer_id: str) -> None:
    """Deleting a customer cancels its subscriptions immediately. Already gone
    counts as done: the outcome the caller needs is 'nothing left to bill'."""
    _ready()
    try:
        stripe.Customer.delete(customer_id)
    except stripe.InvalidRequestError as exc:
        if not _missing(exc):
            raise


def cancel_and_refund(subscription_id: str) -> dict:
    """Cancel now and refund the first paid invoice payment in full.

    Only for the duplicate-subscription guard (spec §6.4). Invoices no longer
    carry their PaymentIntent directly; it is on the invoice's payments.
    """
    _ready()
    sub = stripe.Subscription.cancel(subscription_id)
    invoice_id = sub["latest_invoice"]
    if invoice_id:
        payments = stripe.InvoicePayment.list(invoice=invoice_id, status="paid", limit=10)
        for payment in payments.auto_paging_iter():
            intent = (payment["payment"] or {}).get("payment_intent")
            if intent:
                stripe.Refund.create(
                    payment_intent=intent, idempotency_key=f"duplicate-refund-{subscription_id}"
                )
                break
    return _plain(sub)


def construct_event(payload: bytes, sig_header: str) -> dict:
    """Verify a webhook against the raw body. Raises ValueError on anything
    that is not a correctly signed event, bad JSON included."""
    if not config.stripe_webhook_secret:
        raise ValueError("no webhook secret configured")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, config.stripe_webhook_secret)
    except stripe.SignatureVerificationError as exc:
        raise ValueError("signature verification failed") from exc
    return _plain(event)
```

Replace the `STRIPE_API_VERSION` string with the exact value Step 6 printed.

- [ ] **Step 8: Pin test**

Append to `backend/tests/test_billing_config.py`:

```python
def test_the_sdk_still_speaks_the_api_version_this_code_was_written_for():
    from stripe._api_version import _ApiVersion

    from zgrader import billing_stripe

    assert _ApiVersion.CURRENT == billing_stripe.STRIPE_API_VERSION, (
        "The stripe package now pins a different API version. Re-read "
        "zgrader/billing_stripe.py against that version's changelog before "
        "updating STRIPE_API_VERSION."
    )
```

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_config.py tests/test_compose_env_coverage.py tests/test_lockfile_covers_dependencies.py -v > /tmp/t1.txt 2>&1; echo $?` → `0`. Mutation: change one character of the constant → fails.

- [ ] **Step 9: Commit**

```bash
git add backend/pyproject.toml backend/requirements.lock backend/zgrader/config.py backend/zgrader/billing_stripe.py backend/tests/test_billing_config.py docker-compose.yml .env.example
git commit -m "Add Stripe keys, billing_enabled and the Stripe adapter (billing off by default)"
```

---

### Task 2: Schema — subscriptions, checkout attempts, event ledger

**Files:**
- Modify: `backend/zgrader/models/subscription.py`, `backend/zgrader/models/user.py`, `backend/zgrader/models/plan_entitlement.py`, `backend/zgrader/models/__init__.py`, `backend/tests/test_migrations.py`
- Create: `backend/zgrader/models/checkout_attempt.py`, `backend/zgrader/models/stripe_event.py`, `backend/alembic/versions/9e3b5d1f7a24_stripe_billing.py`, `backend/tests/test_billing_schema.py`

**Interfaces:**
- Produces: `SubscriptionStatus` (str enum, now incl. `unpaid`, `incomplete_expired`, `paused`); `LIVE_STATUSES: tuple[str, ...] = ("active", "trialing", "past_due")`; `NEVER_PAID_STATUSES = ("incomplete", "incomplete_expired")`; `Subscription` columns `status: str`, `founder: bool`, `amount_pence: int | None`, `current_period_start`, `current_period_end`, `cancel_at: datetime | None`, `checkout_attempt_id: UUID | None`, `terms_version: str | None`, `consented_at: datetime | None`.
- Produces: `CheckoutAttempt(user_id, plan, amount_pence, founder, terms_version, consented_at, stripe_session_id, stripe_session_url, expires_at, state)`, constants `ATTEMPT_OPEN/COMPLETED/EXPIRED/ABANDONED`.
- Produces: `StripeEvent(event_id, type, processed_at)`; `User.quota_plan: str | None`; `PlanEntitlement.stripe_product_id: str | None`.

- [ ] **Step 1: Write the failing schema tests**

`backend/tests/test_billing_schema.py`:

```python
"""The shapes billing depends on, in the create_all schema the suite uses.

The partial unique index is declared on the model (not in raw SQL) precisely
so it exists here; tests/test_migrations.py checks the migrated schema has it
too."""

import pytest
from sqlalchemy.exc import IntegrityError

from zgrader.models import Subscription, User, UserRole


def _user(db, email="schema@example.com") -> User:
    user = User(email=email, hashed_password="x", role=UserRole.client, is_verified=True)
    db.add(user)
    db.flush()
    return user


def test_two_live_subscriptions_for_one_user_are_refused(db_session):
    user = _user(db_session)
    db_session.add(Subscription(user_id=user.id, stripe_subscription_id="sub_a", plan="monthly", status="active"))
    db_session.add(Subscription(user_id=user.id, stripe_subscription_id="sub_b", plan="annual", status="past_due"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_an_ended_subscription_does_not_block_a_new_one(db_session):
    user = _user(db_session)
    db_session.add(Subscription(user_id=user.id, stripe_subscription_id="sub_a", plan="monthly", status="canceled"))
    db_session.add(Subscription(user_id=user.id, stripe_subscription_id="sub_b", plan="monthly", status="active"))
    db_session.flush()


def test_status_accepts_stripe_statuses_the_old_enum_lacked(db_session):
    user = _user(db_session)
    row = Subscription(user_id=user.id, stripe_subscription_id="sub_u", plan="monthly", status="unpaid")
    db_session.add(row)
    db_session.flush()
    db_session.refresh(row)
    assert row.status == "unpaid"
```

- [ ] **Step 2: Run — expect failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_schema.py -v > /tmp/t2.txt 2>&1; echo $?; cat /tmp/t2.txt`
Expected: FAIL — the first test does not raise (no index), the third fails on the enum.

- [ ] **Step 3: Rewrite `models/subscription.py`**

```python
"""Billing state, mirrored from Stripe.

Written by exactly one function, zgrader.billing.apply_subscription -- the
webhook, the reconcile sweep and the admin button all call it, so the rules
for what Stripe's state means live in one place.

Deliberately holds no card data of any kind. With Stripe Checkout the card
number never touches this server, which is what keeps PCI scope at its
lightest (SAQ A). There should never be a column here for a card number,
expiry or CVV.
"""

import datetime
import enum
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class SubscriptionStatus(str, enum.Enum):
    """Stripe's subscription statuses. Vocabulary only: the column is a plain
    string, because Stripe adds statuses and adding a value to a Postgres enum
    in a migration is how b7f4c2e19a83 took the stack down. Compare with
    `.value`."""

    active = "active"
    trialing = "trialing"
    past_due = "past_due"
    canceled = "canceled"
    incomplete = "incomplete"
    incomplete_expired = "incomplete_expired"
    unpaid = "unpaid"
    paused = "paused"


#: Statuses in which a subscription is still running and billing. At most one
#: per user (the index below). Includes past_due even after the entitlement
#: grace has run out (see zgrader.entitlements): Stripe is still retrying, so
#: a second subscription would be a second bill.
LIVE_STATUSES: tuple[str, ...] = (
    SubscriptionStatus.active.value,
    SubscriptionStatus.trialing.value,
    SubscriptionStatus.past_due.value,
)

#: Never paid, so never counted as a founder seat.
NEVER_PAID_STATUSES: tuple[str, ...] = (
    SubscriptionStatus.incomplete.value,
    SubscriptionStatus.incomplete_expired.value,
)


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        # Declared here rather than in raw SQL so create_all (the test schema)
        # builds it too -- ix_users_email_lower is the cautionary tale.
        Index(
            "uq_subscriptions_one_live_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('active', 'trialing', 'past_due')"),
        ),
    )

    # ondelete matches the migration, so a schema built by create_all (the
    # test suite) behaves the same as one built by Alembic.
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    plan: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    # Founder seat counting and the account badge.
    founder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # What this subscriber actually pays, read back from Stripe. Makes the
    # founder lock and any later price change visible per subscriber.
    amount_pence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Read from the subscription *item*: current API versions keep the period
    # there. current_period_start also anchors the past_due grace.
    current_period_start: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # When a pending cancellation takes effect. Stripe signals it as cancel_at
    # (flexible billing mode) or cancel_at_period_end (classic); both land here.
    cancel_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checkout_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("checkout_attempts.id", ondelete="SET NULL"), nullable=True
    )
    # Proof of what was agreed at purchase, copied from the checkout attempt.
    terms_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consented_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="subscriptions")  # noqa: F821
```

- [ ] **Step 4: Create `models/checkout_attempt.py`**

```python
"""One row per Checkout session this server starts.

Three jobs in one row: it is the founder-seat hold while a customer is on
Stripe's page, the record of which Terms they accepted and when they consented
to start immediately, and the guard that turns a second Subscribe click (or a
second tab) into the same session rather than a second subscription.
"""

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

ATTEMPT_OPEN = "open"
ATTEMPT_COMPLETED = "completed"
ATTEMPT_EXPIRED = "expired"
# The Stripe call failed after the row was committed; releases any seat.
ATTEMPT_ABANDONED = "abandoned"


class CheckoutAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "checkout_attempts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_pence: Mapped[int] = mapped_column(Integer, nullable=False)
    founder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    terms_version: Mapped[str] = mapped_column(String(20), nullable=False)
    consented_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stripe_session_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    # Kept so a repeat request can be handed the open session without a
    # Stripe round trip.
    stripe_session_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Outlives the Stripe session (31 min) by two minutes, so a founder seat
    # is never released while its session could still complete.
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default=ATTEMPT_OPEN, server_default=ATTEMPT_OPEN)
```

- [ ] **Step 5: Create `models/stripe_event.py`**

```python
"""Every Stripe event this server has acted on, by Stripe's own id.

Written in the same transaction as the event's effect: a duplicate delivery
hits the primary key and does nothing, and a failed one rolls back with its
effect so Stripe's retry does the work for real.
"""

import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from zgrader.db import Base
from zgrader.models.mixins import utcnow


class StripeEvent(Base):
    __tablename__ = "stripe_events"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
```

- [ ] **Step 6: Add `quota_plan`, `stripe_product_id`, register models**

`models/user.py`, after `quota_used`:

```python
    # The plan the current window was counted under. entitlements.get_quota
    # resets the window when the account's plan no longer matches it, so a
    # window is never counted under two plans -- whichever route changed the
    # plan (webhook, reconcile, a grace period simply running out). NULL reads
    # as the free plan, which is what every row written before this was.
    quota_plan: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

`models/plan_entitlement.py`, after `billing_period`:

```python
    # Stripe's Product for this plan, created the first time the plan is sold.
    # A Product carries a name and no amount, so the price still lives only in
    # price_pence -- checkout sends it inline every time.
    stripe_product_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
```

`models/__init__.py`: add imports and `__all__` entries:

```python
from zgrader.models.checkout_attempt import CheckoutAttempt
from zgrader.models.stripe_event import StripeEvent
```

(`"CheckoutAttempt"`, `"StripeEvent"` in `__all__`, alphabetical.) `checkout_attempt` must be imported before `subscription` is used for `create_all` — both are imported by `zgrader.models`, which is enough.

- [ ] **Step 7: Run the schema tests — expect PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_schema.py tests/test_api_quota.py tests/test_api_admin_quota.py -v > /tmp/t2.txt 2>&1; echo $?`
Expected: `0` (existing quota tests still pass with the string status). Mutation: delete the `Index(...)` → first test fails.

Existing tests construct `Subscription(status=SubscriptionStatus.active)`. A `str`-mixin enum member *is* a `str` whose content is `"active"`, so psycopg should store the value — but confirm it: `SELECT DISTINCT status FROM subscriptions` inside one of those tests (or a breakpoint) must show `active`, not `SubscriptionStatus.active`. If it shows the name, change those call sites to `SubscriptionStatus.active.value` rather than weakening the column.

- [ ] **Step 8: Write the migration**

`backend/alembic/versions/9e3b5d1f7a24_stripe_billing.py`:

```python
"""Stripe billing: string status, checkout attempts, event ledger

The subscription status becomes a plain string. Stripe has statuses the enum
never had (unpaid, incomplete_expired, paused), and adding values to a
Postgres enum in a migration is the trap b7f4c2e19a83 fell into -- a string
column with an allow-list in code has no such failure mode.

Nothing has ever written a subscriptions row (no code constructed one before
this release), so the conversion moves no real data; it is written to be
correct if it did.

Revision ID: 9e3b5d1f7a24
Revises: c4f19b7e2d08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "9e3b5d1f7a24"
down_revision = "c4f19b7e2d08"
branch_labels = None
depends_on = None

_OLD_STATUSES = ("active", "trialing", "past_due", "canceled", "incomplete")


def upgrade() -> None:
    op.alter_column(
        "subscriptions",
        "status",
        type_=sa.String(32),
        postgresql_using="status::text",
        existing_nullable=False,
    )
    op.execute("DROP TYPE IF EXISTS subscription_status")

    op.create_table(
        "checkout_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan", sa.String(64), nullable=False),
        sa.Column("amount_pence", sa.Integer(), nullable=False),
        sa.Column("founder", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("terms_version", sa.String(20), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stripe_session_id", sa.String(255), nullable=True, unique=True),
        sa.Column("stripe_session_url", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_checkout_attempts_user_id", "checkout_attempts", ["user_id"])

    op.create_table(
        "stripe_events",
        sa.Column("event_id", sa.String(255), primary_key=True),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.add_column("subscriptions", sa.Column("founder", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("subscriptions", sa.Column("amount_pence", sa.Integer(), nullable=True))
    op.add_column("subscriptions", sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("cancel_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("checkout_attempt_id", sa.Uuid(), nullable=True))
    op.add_column("subscriptions", sa.Column("terms_version", sa.String(20), nullable=True))
    op.add_column("subscriptions", sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_subscriptions_checkout_attempt_id",
        "subscriptions",
        "checkout_attempts",
        ["checkout_attempt_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_subscriptions_one_live_per_user",
        "subscriptions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('active', 'trialing', 'past_due')"),
    )

    op.add_column("users", sa.Column("quota_plan", sa.String(64), nullable=True))
    op.add_column("plan_entitlements", sa.Column("stripe_product_id", sa.String(64), nullable=True))
    op.create_unique_constraint(
        "uq_plan_entitlements_stripe_product_id", "plan_entitlements", ["stripe_product_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_plan_entitlements_stripe_product_id", "plan_entitlements", type_="unique")
    op.drop_column("plan_entitlements", "stripe_product_id")
    op.drop_column("users", "quota_plan")

    op.drop_index("uq_subscriptions_one_live_per_user", table_name="subscriptions")
    op.drop_constraint("fk_subscriptions_checkout_attempt_id", "subscriptions", type_="foreignkey")
    for column in (
        "consented_at",
        "terms_version",
        "checkout_attempt_id",
        "cancel_at",
        "current_period_start",
        "amount_pence",
        "founder",
    ):
        op.drop_column("subscriptions", column)

    op.drop_table("stripe_events")
    op.drop_index("ix_checkout_attempts_user_id", table_name="checkout_attempts")
    op.drop_table("checkout_attempts")

    # Statuses the old enum cannot hold collapse to canceled -- the one old
    # value that grants nothing.
    listed = ", ".join(f"'{s}'" for s in _OLD_STATUSES)
    op.execute(f"UPDATE subscriptions SET status = 'canceled' WHERE status NOT IN ({listed})")
    # postgresql.ENUM, not sa.Enum: only the dialect type honours create_type.
    postgresql.ENUM(*_OLD_STATUSES, name="subscription_status").create(op.get_bind(), checkfirst=True)
    op.alter_column(
        "subscriptions",
        "status",
        type_=postgresql.ENUM(*_OLD_STATUSES, name="subscription_status", create_type=False),
        postgresql_using="status::subscription_status",
        existing_nullable=False,
    )
```

- [ ] **Step 9: Assert the migrated schema, then run the migration tests**

Append to `backend/tests/test_migrations.py`:

```python
def test_the_billing_migration_leaves_the_constraints_billing_relies_on(scratch_database):
    """The partial index is what stops two live subscriptions for one person,
    and the enum must be gone or a Stripe status it lacks fails the webhook."""
    _alembic(scratch_database, "upgrade", "head")

    assert _query(
        scratch_database,
        "SELECT 1 FROM pg_indexes WHERE indexname = 'uq_subscriptions_one_live_per_user'",
    ), "no one-live-subscription-per-user index"
    assert not _query(
        scratch_database, "SELECT 1 FROM pg_type WHERE typname = 'subscription_status'"
    ), "the subscription_status enum survived the migration"
```

Run: `./.venv/Scripts/python.exe -m pytest tests/test_migrations.py -v > /tmp/t2.txt 2>&1; echo $?`
Expected: `0` — including `test_the_head_migration_can_be_reversed_and_reapplied`, which exercises this downgrade, and `test_the_migrated_schema_has_the_tables_the_models_declare`.

- [ ] **Step 10: Full suite, then commit**

Run: `./.venv/Scripts/python.exe -m pytest -q > /tmp/full.txt 2>&1; echo $?` → `0`.

```bash
git add backend/zgrader/models backend/alembic/versions/9e3b5d1f7a24_stripe_billing.py backend/tests/test_billing_schema.py backend/tests/test_migrations.py
git commit -m "Billing schema: string subscription status, checkout attempts, Stripe event ledger"
```

---

### Task 3: Entitlement — bounded `past_due` grace and the derived window reset

**Files:**
- Modify: `backend/zgrader/entitlements.py`
- Create: `backend/tests/test_entitlements_billing.py`

**Interfaces:**
- Consumes: `LIVE_STATUSES`, `SubscriptionStatus`, `Subscription.current_period_start`, `User.quota_plan` (Task 2).
- Produces: `entitlements.PAST_DUE_GRACE: timedelta` (21 days); `entitlements.is_entitled(sub: Subscription, now: datetime) -> bool`; `entitlements.entitled_subscription(db, user, now=None) -> Subscription | None`. `active_plan`, `get_quota`, `consume_submission` keep their signatures.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_entitlements_billing.py`:

```python
"""What a subscription status grants, and what a plan change does to quota.

The grace-period tests pin the anchor, not just the length: when a renewal
fails, Stripe has already moved the subscription into the new period, so an
end-anchored grace would hand out a month -- or a year -- of unpaid access.
"""

import datetime

from zgrader import entitlements
from zgrader.models import Subscription, User, UserRole

NOW = datetime.datetime.now(datetime.timezone.utc)
DAY = datetime.timedelta(days=1)


def _user(db, **kw) -> User:
    user = User(email=kw.pop("email", "ent@example.com"), hashed_password="x", role=UserRole.client, is_verified=True, **kw)
    db.add(user)
    db.flush()
    return user


def _sub(db, user, status, *, start=NOW - DAY, end=NOW + 29 * DAY, plan="monthly", sid="sub_1"):
    row = Subscription(
        user_id=user.id, stripe_subscription_id=sid, plan=plan, status=status,
        current_period_start=start, current_period_end=end,
    )
    db.add(row)
    db.flush()
    return row


def test_active_and_trialing_are_entitled(db_session):
    user = _user(db_session)
    _sub(db_session, user, "trialing")
    assert entitlements.active_plan(db_session, user) == "monthly"


def test_past_due_is_entitled_inside_the_grace(db_session):
    user = _user(db_session)
    _sub(db_session, user, "past_due", start=NOW - 10 * DAY)
    assert entitlements.active_plan(db_session, user) == "monthly"


def test_past_due_grace_counts_from_the_failed_renewal_not_the_period_end(db_session):
    # 30 days since the renewal failed; the new period still has a day to run.
    # End-anchored, this would still be entitled for 22 more days.
    user = _user(db_session)
    _sub(db_session, user, "past_due", start=NOW - 30 * DAY, end=NOW + DAY)
    assert entitlements.active_plan(db_session, user) == "free"


def test_unpaid_and_canceled_are_not_entitled(db_session):
    user = _user(db_session)
    _sub(db_session, user, "unpaid", sid="sub_u")
    _sub(db_session, user, "canceled", sid="sub_c")
    assert entitlements.active_plan(db_session, user) == "free"


def test_subscribing_starts_a_fresh_window(db_session):
    user = _user(db_session, quota_used=3, quota_period_started_at=NOW - DAY)
    _sub(db_session, user, "active")
    quota = entitlements.get_quota(db_session, user)
    assert (quota.plan, quota.used) == ("monthly", 0)
    assert user.quota_period_started_at is None
    assert user.quota_plan == "monthly"


def test_a_grace_running_out_resets_the_window_with_no_write_in_between(db_session):
    """Nothing writes when a grace period expires -- the plan changes because
    time passed. Only a reset derived on read can catch that."""
    user = _user(db_session, quota_used=40, quota_period_started_at=NOW - 5 * DAY, quota_plan="monthly")
    _sub(db_session, user, "past_due", start=NOW - 22 * DAY)
    quota = entitlements.get_quota(db_session, user)
    assert (quota.plan, quota.used, quota.can_submit) == ("free", 0, True)
    assert user.quota_plan == "free"


def test_an_unchanged_plan_keeps_its_window(db_session):
    started = NOW - DAY
    user = _user(db_session, quota_used=2, quota_period_started_at=started)
    quota = entitlements.get_quota(db_session, user)
    assert quota.used == 2
    assert user.quota_period_started_at == started
```

- [ ] **Step 2: Run — expect failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_entitlements_billing.py -v > /tmp/t3.txt 2>&1; echo $?; cat /tmp/t3.txt`
Expected: FAIL — `past_due` tests (never entitled today), reset tests (`quota_plan` never set).

- [ ] **Step 3: Implement**

In `backend/zgrader/entitlements.py` replace the import of `SubscriptionStatus` and `_ENTITLED_STATUSES` and `active_plan`:

```python
from zgrader.models.subscription import LIVE_STATUSES, Subscription, SubscriptionStatus

#: How long a failed renewal keeps paid access while Stripe retries. Bounded
#: here rather than trusted to the Dashboard: Stripe's "when retries run out"
#: is a setting, and left at "leave it past due" an unbounded rule would grant
#: access forever. The go-live checklist still sets it to cancel.
PAST_DUE_GRACE = datetime.timedelta(days=21)


def _aware(value: datetime.datetime) -> datetime.datetime:
    return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)


def is_entitled(sub: Subscription, now: datetime.datetime) -> bool:
    """Whether this subscription grants its plan right now.

    past_due counts from current_period_start -- the renewal that failed. By
    the time a renewal fails Stripe has already advanced the subscription into
    the new period, so current_period_end is a whole period away.
    """
    if sub.status in (SubscriptionStatus.active.value, SubscriptionStatus.trialing.value):
        return True
    if sub.status == SubscriptionStatus.past_due.value and sub.current_period_start is not None:
        return now < _aware(sub.current_period_start) + PAST_DUE_GRACE
    return False


def entitled_subscription(db: Session, user: User, now: datetime.datetime | None = None) -> Subscription | None:
    now = now or _now()
    live = (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id, Subscription.status.in_(LIVE_STATUSES))
        .all()
    )
    return next((sub for sub in live if is_entitled(sub, now)), None)


def active_plan(db: Session, user: User) -> str:
    """The plan this account is on -- its entitled subscription, or free."""
    subscription = entitled_subscription(db, user)
    return subscription.plan if subscription else FREE_PLAN
```

Add the reset helper above `get_quota`:

```python
def _reset_if_plan_changed(user: User, plan: str) -> None:
    """A window belongs to the plan it was counted under.

    Derived on read rather than performed by whatever changed the plan, so
    every route is covered -- a webhook, reconcile, an operator, or a grace
    period simply running out with nobody writing anything. Mutates `user`;
    the caller owns the flush, same as the rollover below.
    """
    if (user.quota_plan or FREE_PLAN) == plan:
        return
    user.quota_used = 0
    user.quota_period_started_at = None
    user.quota_plan = plan
```

In `get_quota`, call it immediately after `plan = active_plan(db, user)` — *before* the unlimited early return, so an unlimited plan still records itself and lapsing back to free starts clean:

```python
    plan = active_plan(db, user)
    _reset_if_plan_changed(user, plan)
    limit, period_days = _plan_rules(db, plan)
```

- [ ] **Step 4: Run — expect PASS; mutation-check**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_entitlements_billing.py tests/test_api_quota.py tests/test_api_admin_quota.py -v > /tmp/t3.txt 2>&1; echo $?` → `0`.
Mutations: anchor on `current_period_end` → the "failed renewal" test fails; delete the `_reset_if_plan_changed` call → both reset tests fail.

- [ ] **Step 5: Commit**

```bash
git add backend/zgrader/entitlements.py backend/tests/test_entitlements_billing.py
git commit -m "Entitle past_due for 21 days from the failed renewal; reset quota when the plan changes"
```

---

### Task 4: `apply_subscription` — the one writer

**Files:**
- Create: `backend/zgrader/billing.py`, `backend/tests/billing_fakes.py`, `backend/tests/test_billing_apply.py`

**Interfaces:**
- Consumes: Task 1 adapter (`billing_stripe.cancel_and_refund`), Task 2 models.
- Produces: `billing.apply_subscription(db: Session, obj: dict, *, source: str = "webhook") -> bool` — returns whether anything changed; never commits (caller does). `billing.BillingRefused(status_code: int, message: str)` exception.
- Produces (tests): `tests.billing_fakes.FakeStripe` with `.install(monkeypatch)`, `.subscriptions: dict[str, dict]`, `.calls: list[tuple[str, dict]]`, `.fail: set[str]`; `subscription_obj(...) -> dict`; `enable_billing(monkeypatch)`.

- [ ] **Step 1: Write the fakes**

`backend/tests/billing_fakes.py`:

```python
"""A stand-in for zgrader.billing_stripe -- the only thing tests replace.

Everything above the adapter runs for real, including webhook signature
verification (construct_event is deliberately NOT faked; tests sign payloads
with the real scheme instead -- see sign()).
"""

import datetime
import hashlib
import hmac
import itertools
import time

from zgrader import billing_stripe
from zgrader.config import config

WEBHOOK_SECRET = "whsec_test_secret"
_counter = itertools.count(1)


def enable_billing(monkeypatch) -> None:
    monkeypatch.setattr(config, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(config, "stripe_webhook_secret", WEBHOOK_SECRET)


def _epoch(value: datetime.datetime) -> int:
    return int(value.timestamp())


def subscription_obj(
    *,
    user_id,
    sub_id: str = "sub_1",
    customer: str = "cus_1",
    plan: str = "monthly",
    status: str = "active",
    founder: bool = False,
    attempt_id=None,
    amount: int = 500,
    period_start: datetime.datetime | None = None,
    period_end: datetime.datetime | None = None,
    cancel_at: datetime.datetime | None = None,
    cancel_at_period_end: bool = False,
) -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    start = period_start or now
    end = period_end or now + datetime.timedelta(days=30)
    metadata = {"user_id": str(user_id), "plan": plan, "founder": "true" if founder else "false"}
    if attempt_id is not None:
        metadata["checkout_attempt_id"] = str(attempt_id)
    return {
        "id": sub_id,
        "object": "subscription",
        "customer": customer,
        "status": status,
        "metadata": metadata,
        "cancel_at": _epoch(cancel_at) if cancel_at else None,
        "cancel_at_period_end": cancel_at_period_end,
        "latest_invoice": "in_1",
        "items": {
            "data": [
                {
                    "price": {"unit_amount": amount},
                    "current_period_start": _epoch(start),
                    "current_period_end": _epoch(end),
                }
            ]
        },
    }


def sign(payload: bytes, secret: str = WEBHOOK_SECRET, timestamp: int | None = None) -> str:
    """Stripe's real signature scheme: HMAC-SHA256 over "{t}.{body}"."""
    ts = timestamp or int(time.time())
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


class FakeStripe:
    def __init__(self) -> None:
        self.subscriptions: dict[str, dict] = {}
        self.calls: list[tuple[str, dict]] = []
        # Names of adapter functions that should raise on their next call.
        self.fail: set[str] = set()

    def _record(self, name: str, **kw) -> None:
        self.calls.append((name, kw))
        if name in self.fail:
            raise RuntimeError(f"fake Stripe failure in {name}")

    def called(self, name: str) -> list[dict]:
        return [kw for n, kw in self.calls if n == name]

    def install(self, monkeypatch) -> "FakeStripe":
        for name in (
            "create_customer", "create_product", "create_checkout_session",
            "create_portal_session", "retrieve_subscription", "list_subscriptions",
            "delete_customer", "cancel_and_refund",
        ):
            monkeypatch.setattr(billing_stripe, name, getattr(self, name))
        return self

    def create_customer(self, *, user_id, email):
        self._record("create_customer", user_id=user_id, email=email)
        return {"id": f"cus_{user_id[:8]}"}

    def create_product(self, *, plan, name):
        self._record("create_product", plan=plan, name=name)
        return {"id": f"prod_{plan}"}

    def create_checkout_session(self, **params):
        self._record("create_checkout_session", **params)
        n = next(_counter)
        return {"id": f"cs_test_{n}", "url": f"https://checkout.stripe.test/c/{n}"}

    def create_portal_session(self, *, customer, return_url):
        self._record("create_portal_session", customer=customer, return_url=return_url)
        return {"url": f"https://billing.stripe.test/p/{customer}"}

    def retrieve_subscription(self, subscription_id):
        self._record("retrieve_subscription", subscription_id=subscription_id)
        return self.subscriptions.get(subscription_id)

    def list_subscriptions(self):
        self._record("list_subscriptions")
        return iter(list(self.subscriptions.values()))

    def delete_customer(self, customer_id):
        self._record("delete_customer", customer_id=customer_id)

    def cancel_and_refund(self, subscription_id):
        self._record("cancel_and_refund", subscription_id=subscription_id)
        sub = dict(self.subscriptions[subscription_id], status="canceled")
        self.subscriptions[subscription_id] = sub
        return sub
```

- [ ] **Step 2: Write the failing tests**

`backend/tests/test_billing_apply.py`:

```python
"""apply_subscription: the only code that writes billing state."""

import datetime

import pytest

from tests.billing_fakes import FakeStripe, enable_billing, subscription_obj
from zgrader import billing
from zgrader.models import AuditLog, Subscription, User, UserRole
from zgrader.models.checkout_attempt import ATTEMPT_COMPLETED, CheckoutAttempt

NOW = datetime.datetime.now(datetime.timezone.utc)


@pytest.fixture()
def fake(monkeypatch):
    enable_billing(monkeypatch)
    return FakeStripe().install(monkeypatch)


def _customer(db, email="apply@example.com", cus="cus_1") -> User:
    user = User(email=email, hashed_password="x", role=UserRole.client, is_verified=True, stripe_customer_id=cus)
    db.add(user)
    db.flush()
    return user


def _audits(db, action):
    return db.query(AuditLog).filter(AuditLog.action == action).all()


def test_a_new_subscription_is_mirrored_and_audited(db_session, fake):
    user = _customer(db_session)
    start, end = NOW.replace(microsecond=0), (NOW + datetime.timedelta(days=365)).replace(microsecond=0)
    obj = subscription_obj(user_id=user.id, plan="annual", founder=True, amount=3000, period_start=start, period_end=end)

    assert billing.apply_subscription(db_session, obj) is True

    row = db_session.query(Subscription).one()
    assert (row.plan, row.status, row.founder, row.amount_pence) == ("annual", "active", True, 3000)
    assert (row.current_period_start, row.current_period_end) == (start, end)
    assert len(_audits(db_session, "subscription_started")) == 1


def test_reapplying_the_same_state_changes_nothing(db_session, fake):
    user = _customer(db_session)
    obj = subscription_obj(user_id=user.id)
    billing.apply_subscription(db_session, obj)
    assert billing.apply_subscription(db_session, obj) is False
    assert len(_audits(db_session, "subscription_changed")) == 0


def test_metadata_naming_someone_elses_customer_is_ignored(db_session, fake):
    user = _customer(db_session, cus="cus_mine")
    obj = subscription_obj(user_id=user.id, customer="cus_someone_else")
    assert billing.apply_subscription(db_session, obj) is False
    assert db_session.query(Subscription).count() == 0


def test_an_unknown_user_is_ignored(db_session, fake):
    import uuid

    assert billing.apply_subscription(db_session, subscription_obj(user_id=uuid.uuid4())) is False
    assert db_session.query(Subscription).count() == 0


def test_classic_cancel_at_period_end_becomes_a_cancel_date(db_session, fake):
    user = _customer(db_session)
    end = (NOW + datetime.timedelta(days=10)).replace(microsecond=0)
    billing.apply_subscription(db_session, subscription_obj(user_id=user.id, period_end=end, cancel_at_period_end=True))
    assert db_session.query(Subscription).one().cancel_at == end


def test_ending_is_audited_without_an_email_address(db_session, fake):
    user = _customer(db_session)
    billing.apply_subscription(db_session, subscription_obj(user_id=user.id))
    billing.apply_subscription(db_session, subscription_obj(user_id=user.id, status="canceled"))
    ended = _audits(db_session, "subscription_ended")
    assert len(ended) == 1
    for row in db_session.query(AuditLog).filter(AuditLog.action.like("subscription_%")).all():
        assert "@" not in str(row.detail)


def test_a_second_live_subscription_is_cancelled_and_refunded(db_session, fake):
    user = _customer(db_session)
    billing.apply_subscription(db_session, subscription_obj(user_id=user.id, sub_id="sub_old"))
    fake.subscriptions["sub_new"] = subscription_obj(user_id=user.id, sub_id="sub_new")

    billing.apply_subscription(db_session, fake.subscriptions["sub_new"])
    db_session.flush()  # the partial unique index must not fire

    assert [c["subscription_id"] for c in fake.called("cancel_and_refund")] == ["sub_new"]
    statuses = {r.stripe_subscription_id: r.status for r in db_session.query(Subscription)}
    assert statuses == {"sub_old": "active", "sub_new": "canceled"}
    assert len(_audits(db_session, "subscription_duplicate_refunded")) == 1


def test_the_checkout_attempt_carries_its_consent_onto_the_subscription(db_session, fake):
    user = _customer(db_session)
    attempt = CheckoutAttempt(
        user_id=user.id, plan="monthly", amount_pence=500, founder=False, terms_version="2026-09",
        consented_at=NOW, expires_at=NOW + datetime.timedelta(minutes=33), stripe_session_id="cs_1",
    )
    db_session.add(attempt)
    db_session.flush()

    billing.apply_subscription(db_session, subscription_obj(user_id=user.id, attempt_id=attempt.id))

    row = db_session.query(Subscription).one()
    assert (row.checkout_attempt_id, row.terms_version, row.consented_at) == (attempt.id, "2026-09", NOW)
    assert attempt.state == ATTEMPT_COMPLETED
```

- [ ] **Step 3: Run — expect failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_apply.py -v > /tmp/t4.txt 2>&1; echo $?; cat /tmp/t4.txt`
Expected: FAIL — `ModuleNotFoundError: zgrader.billing`.

- [ ] **Step 4: Implement `billing.py` (writer half)**

`backend/zgrader/billing.py`:

```python
"""Billing: what Stripe's state means for an account.

apply_subscription is the only code that writes `subscriptions`. The webhook,
the reconcile sweep and the admin reconcile button all end here, so there is
one set of rules and nowhere for a second, slightly different set to grow.

Nothing in this module trusts a figure from the browser or from an event
payload: amounts come from our own rows on the way out and from a fresh read
of Stripe on the way back.
"""

import datetime
import logging
import uuid

from sqlalchemy.orm import Session

from zgrader import billing_stripe
from zgrader.models import AuditLog, User
from zgrader.models.checkout_attempt import ATTEMPT_COMPLETED, ATTEMPT_OPEN, CheckoutAttempt
from zgrader.models.subscription import LIVE_STATUSES, Subscription

logger = logging.getLogger(__name__)


class BillingRefused(Exception):
    """A billing request the caller should be told no about, with the HTTP
    status that says why."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _ts(value: int | None) -> datetime.datetime | None:
    return datetime.datetime.fromtimestamp(value, tz=datetime.timezone.utc) if value else None


def _first_item(obj: dict) -> dict:
    items = (obj.get("items") or {}).get("data") or []
    return items[0] if items else {}


def _cancel_at(obj: dict) -> datetime.datetime | None:
    # Flexible billing mode sets cancel_at; classic sets cancel_at_period_end.
    if obj.get("cancel_at"):
        return _ts(obj["cancel_at"])
    if obj.get("cancel_at_period_end"):
        return _ts(_first_item(obj).get("current_period_end"))
    return None


def _audit(db: Session, user_id, action: str, detail: dict) -> None:
    # Never an email address in detail: delete_account scrubs addresses by key
    # name, so one under any new key would survive an erasure.
    db.add(AuditLog(user_id=user_id, action=action, detail=detail))


def _owner(db: Session, obj: dict) -> User | None:
    metadata = obj.get("metadata") or {}
    try:
        user_id = uuid.UUID(str(metadata.get("user_id")))
    except ValueError:
        logger.info("subscription %s has no user in its metadata; not ours to mirror", obj.get("id"))
        return None
    user = db.get(User, user_id)
    if user is None:
        # An account deleted since -- its customer, and so this subscription,
        # were cancelled on the way out.
        logger.info("subscription %s names a user that no longer exists", obj.get("id"))
        return None
    if user.stripe_customer_id != obj.get("customer"):
        logger.warning(
            "subscription %s: metadata user %s does not own customer %s; ignoring",
            obj.get("id"), user.id, obj.get("customer"),
        )
        return None
    return user


def _other_live(db: Session, user_id, subscription_id: str) -> Subscription | None:
    return (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user_id,
            Subscription.status.in_(LIVE_STATUSES),
            Subscription.stripe_subscription_id != subscription_id,
        )
        .first()
    )


def _link_attempt(db: Session, row: Subscription, obj: dict, user: User) -> None:
    raw = (obj.get("metadata") or {}).get("checkout_attempt_id")
    if not raw or row.checkout_attempt_id is not None:
        return
    try:
        attempt = db.get(CheckoutAttempt, uuid.UUID(raw))
    except ValueError:
        return
    if attempt is None or attempt.user_id != user.id:
        return
    row.checkout_attempt_id = attempt.id
    row.terms_version = attempt.terms_version
    row.consented_at = attempt.consented_at
    if attempt.state == ATTEMPT_OPEN:
        attempt.state = ATTEMPT_COMPLETED


def apply_subscription(db: Session, obj: dict, *, source: str = "webhook") -> bool:
    """Mirror one subscription, as just read from Stripe. Returns whether
    anything changed. Flushes; never commits -- the caller owns the
    transaction, which is what lets the webhook record its event in the same
    one."""
    user = _owner(db, obj)
    if user is None:
        return False

    # Before any write: the partial unique index would otherwise reject the
    # upsert and the event would 500 on every retry for days.
    if obj["status"] in LIVE_STATUSES and _other_live(db, user.id, obj["id"]) is not None:
        obj = billing_stripe.cancel_and_refund(obj["id"])
        _audit(db, user.id, "subscription_duplicate_refunded", {"stripe_subscription_id": obj["id"]})

    metadata = obj.get("metadata") or {}
    item = _first_item(obj)
    row = db.query(Subscription).filter(Subscription.stripe_subscription_id == obj["id"]).first()
    created = row is None
    if created:
        row = Subscription(user_id=user.id, stripe_subscription_id=obj["id"])
        db.add(row)
    before = None if created else (row.status, row.plan, row.founder, row.amount_pence, row.cancel_at,
                                   row.current_period_start, row.current_period_end)

    row.plan = metadata.get("plan") or row.plan or "unknown"
    row.founder = metadata.get("founder") == "true"
    row.status = obj["status"]
    row.amount_pence = (item.get("price") or {}).get("unit_amount")
    row.current_period_start = _ts(item.get("current_period_start"))
    row.current_period_end = _ts(item.get("current_period_end"))
    row.cancel_at = _cancel_at(obj)
    _link_attempt(db, row, obj, user)

    after = (row.status, row.plan, row.founder, row.amount_pence, row.cancel_at,
             row.current_period_start, row.current_period_end)
    changed = created or before != after
    if changed:
        detail = {
            "stripe_subscription_id": obj["id"],
            "plan": row.plan,
            "founder": row.founder,
            "status_before": None if before is None else before[0],
            "status_after": row.status,
            "source": source,
        }
        if created:
            action = "subscription_started"
        elif before[0] in LIVE_STATUSES and row.status not in LIVE_STATUSES:
            action = "subscription_ended"
        else:
            action = "subscription_changed"
        _audit(db, user.id, action, detail)
        if source == "reconcile":
            _audit(db, user.id, "billing_reconciled", detail)
            logger.warning("reconcile corrected subscription %s (%s)", obj["id"], action)
    db.flush()
    return changed
```

- [ ] **Step 5: Run — expect PASS; mutation-check**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_apply.py -v > /tmp/t4.txt 2>&1; echo $?` → `0`.
Mutations: remove the customer check in `_owner` → mismatch test fails; move the duplicate guard below the upsert → duplicate test fails with `IntegrityError`; drop the `cancel_at_period_end` branch → cancel-date test fails.

- [ ] **Step 6: Commit**

```bash
git add backend/zgrader/billing.py backend/tests/billing_fakes.py backend/tests/test_billing_apply.py
git commit -m "Add apply_subscription, the single writer of billing state"
```

---

### Task 5: Checkout and founder seats

**Files:**
- Modify: `backend/zgrader/billing.py`, `backend/zgrader/api/main.py`, `backend/zgrader/api/routers/auth.py` (terms version only)
- Create: `backend/zgrader/schemas/billing.py`, `backend/zgrader/api/routers/billing.py`, `backend/tests/test_billing_checkout.py`

**Interfaces:**
- Consumes: `apply_subscription`, `BillingRefused` (Task 4); adapter (Task 1); models (Task 2); `entitlements.entitled_subscription` (Task 3).
- Produces: `billing.SESSION_LIFETIME = timedelta(minutes=31)`, `billing.HOLD_LIFETIME = timedelta(minutes=33)`; `billing.founder_seats_taken(db, now) -> int`; `billing.founder_seats_remaining(db, settings, now=None) -> int | None`; `billing._decide_and_insert(db, user, plan, *, terms_version, now) -> CheckoutAttempt` (locks, decides, inserts, **no commit**); `billing.reserve_attempt(...)` (same, commits); `billing.create_checkout(db, user, *, plan_name, terms_version) -> str`.
- Produces: `schemas.billing.CheckoutIn {plan, terms_version, immediate_start_consent}` (`extra="forbid"`), `CheckoutOut {url}`, `PortalOut {url}`, `SubscriptionOut`, `ReconcileOut {checked, corrected}`; router `zgrader.api.routers.billing.router` (prefix `/billing`).
- Produces: `auth.CURRENT_TERMS_VERSION = "2026-09"`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_billing_checkout.py`:

```python
"""POST /billing/checkout: refusals, amounts, founder seats, two tabs."""

import datetime
import threading

import pytest
from fastapi.testclient import TestClient

from tests.billing_fakes import FakeStripe, enable_billing
from tests.conftest import register_and_verify
from zgrader import billing
from zgrader.api.main import app
from zgrader.api.routers.auth import CURRENT_TERMS_VERSION
from zgrader.db import SessionLocal
from zgrader.models import PlanEntitlement, Settings, Subscription, User
from zgrader.models.checkout_attempt import ATTEMPT_ABANDONED, CheckoutAttempt

client = TestClient(app)
NOW = datetime.datetime.now(datetime.timezone.utc)


@pytest.fixture()
def fake(monkeypatch):
    enable_billing(monkeypatch)
    return FakeStripe().install(monkeypatch)


def _body(plan="monthly", **overrides):
    return {"plan": plan, "terms_version": CURRENT_TERMS_VERSION, "immediate_start_consent": True, **overrides}


def _auth(email="buyer@example.com"):
    return {"Authorization": f"Bearer {register_and_verify(client, email)}"}


def _user(db, email="buyer@example.com") -> User:
    db.expire_all()
    return db.query(User).filter(User.email == email).one()


def test_billing_off_is_404(db_session):
    assert client.post("/billing/checkout", json=_body(), headers=_auth()).status_code == 404


def test_an_amount_from_the_client_is_rejected(db_session, fake):
    resp = client.post("/billing/checkout", json=_body(amount_pence=1), headers=_auth())
    assert resp.status_code == 422
    assert fake.called("create_checkout_session") == []


@pytest.mark.parametrize(
    "overrides", [{"terms_version": "2000-01"}, {"immediate_start_consent": False}, {"plan": "pack"}, {"plan": "free"}, {"plan": "nope"}]
)
def test_refused_before_reaching_stripe(db_session, fake, overrides):
    resp = client.post("/billing/checkout", json=_body(**overrides), headers=_auth())
    assert resp.status_code == 422
    assert fake.calls == []


def test_an_unverified_account_is_refused(db_session, fake):
    """Same gate as submitting: an address nobody has confirmed does not get
    to start a payment in the account's name."""
    client.post("/auth/register", json={"email": "unv@example.com", "password": "hunter2pass", "accept_terms": True})
    token = client.post("/auth/login", data={"username": "unv@example.com", "password": "hunter2pass"}).json()["access_token"]
    resp = client.post("/billing/checkout", json=_body(), headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert fake.calls == []


def test_a_live_subscription_is_409(db_session, fake):
    headers = _auth()
    user = _user(db_session)
    db_session.add(Subscription(user_id=user.id, stripe_subscription_id="sub_x", plan="monthly", status="past_due"))
    db_session.commit()
    assert client.post("/billing/checkout", json=_body(), headers=headers).status_code == 409


def test_the_amount_is_the_plans_own_price(db_session, fake):
    resp = client.post("/billing/checkout", json=_body("monthly"), headers=_auth())
    assert resp.status_code == 200, resp.text
    assert resp.json()["url"].startswith("https://checkout.stripe.test/")

    (params,) = fake.called("create_checkout_session")
    price = db_session.query(PlanEntitlement).filter_by(plan="monthly").one().price_pence
    line = params["line_items"][0]["price_data"]
    assert (line["unit_amount"], line["currency"], line["recurring"]) == (price, "gbp", {"interval": "month"})
    meta = params["subscription_data"]["metadata"]
    user = _user(db_session)
    assert (meta["user_id"], meta["plan"], meta["founder"]) == (str(user.id), "monthly", "false")
    assert user.stripe_customer_id


def test_a_second_request_gets_the_same_session(db_session, fake):
    headers = _auth()
    first = client.post("/billing/checkout", json=_body(), headers=headers).json()["url"]
    second = client.post("/billing/checkout", json=_body(), headers=headers).json()["url"]
    assert first == second
    assert len(fake.called("create_checkout_session")) == 1
    assert len(fake.called("create_customer")) == 1


def test_annual_gets_the_founder_price_while_seats_remain(db_session, fake):
    client.post("/billing/checkout", json=_body("annual"), headers=_auth())
    (params,) = fake.called("create_checkout_session")
    settings = db_session.query(Settings).one()
    assert params["line_items"][0]["price_data"]["unit_amount"] == settings.founder_price_pence
    assert params["subscription_data"]["metadata"]["founder"] == "true"


def test_no_seats_left_means_full_price(db_session, fake):
    db_session.query(Settings).one().founder_seats = 0
    db_session.commit()
    client.post("/billing/checkout", json=_body("annual"), headers=_auth())
    (params,) = fake.called("create_checkout_session")
    annual = db_session.query(PlanEntitlement).filter_by(plan="annual").one()
    assert params["line_items"][0]["price_data"]["unit_amount"] == annual.price_pence


def test_monthly_is_never_founder_priced(db_session, fake):
    client.post("/billing/checkout", json=_body("monthly"), headers=_auth())
    (params,) = fake.called("create_checkout_session")
    assert params["subscription_data"]["metadata"]["founder"] == "false"


def test_a_stripe_failure_releases_the_seat(db_session, fake):
    fake.fail.add("create_checkout_session")
    settings = db_session.query(Settings).one()
    before = billing.founder_seats_remaining(db_session, settings)
    assert client.post("/billing/checkout", json=_body("annual"), headers=_auth()).status_code == 503
    db_session.expire_all()
    assert db_session.query(CheckoutAttempt).one().state == ATTEMPT_ABANDONED
    assert billing.founder_seats_remaining(db_session, db_session.query(Settings).one()) == before


def test_the_last_seat_cannot_be_taken_twice(db_session, fake):
    """Two sessions, as two concurrent requests would be. A decides under the
    Settings row lock and has not committed; B must wait for it, and then see
    the seat gone. Without FOR UPDATE, B does not block and both get it."""
    db_session.query(Settings).one().founder_seats = 1
    db_session.commit()
    register_and_verify(client, "a@example.com")
    register_and_verify(client, "b@example.com")

    a, b = SessionLocal(), SessionLocal()
    try:
        user_a = a.query(User).filter_by(email="a@example.com").one()
        user_b = b.query(User).filter_by(email="b@example.com").one()
        plan_a = a.query(PlanEntitlement).filter_by(plan="annual").one()
        plan_b = b.query(PlanEntitlement).filter_by(plan="annual").one()

        held = billing._decide_and_insert(a, user_a, plan_a, terms_version=CURRENT_TERMS_VERSION, now=NOW)
        result = {}
        worker = threading.Thread(
            target=lambda: result.update(
                b=billing.reserve_attempt(b, user_b, plan_b, terms_version=CURRENT_TERMS_VERSION, now=NOW)
            )
        )
        worker.start()
        worker.join(timeout=1.0)
        assert worker.is_alive(), "B did not wait for A's lock -- the seat count is racy"

        a.commit()
        worker.join(timeout=10.0)
        assert held.founder is True
        assert result["b"].founder is False
    finally:
        a.close()
        b.close()
```

- [ ] **Step 2: Run — expect failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_checkout.py -v > /tmp/t5.txt 2>&1; echo $?; cat /tmp/t5.txt`
Expected: FAIL — `/billing/checkout` 404s for every case (route does not exist), so the "billing off" test passes for the wrong reason and every other test fails.

- [ ] **Step 3: Bump the Terms version**

In `backend/zgrader/api/routers/auth.py`: `CURRENT_TERMS_VERSION = "2026-09"` (the Terms change in Task 13 of this same PR).

- [ ] **Step 4: Schemas**

`backend/zgrader/schemas/billing.py`:

```python
import datetime

from pydantic import BaseModel, ConfigDict, Field


class CheckoutIn(BaseModel):
    """The browser names a plan and confirms consent. It never sends a
    figure: extra="forbid" makes a client-supplied amount a 422 rather than
    something quietly ignored."""

    model_config = ConfigDict(extra="forbid")

    plan: str = Field(min_length=1, max_length=64)
    terms_version: str = Field(min_length=1, max_length=20)
    immediate_start_consent: bool


class CheckoutOut(BaseModel):
    url: str


class PortalOut(BaseModel):
    url: str


class SubscriptionOut(BaseModel):
    plan: str
    status: str
    entitled: bool
    founder: bool
    amount_pence: int | None
    current_period_start: datetime.datetime | None
    current_period_end: datetime.datetime | None
    cancel_at: datetime.datetime | None


class ReconcileOut(BaseModel):
    checked: int
    corrected: int
```

- [ ] **Step 5: Checkout logic**

Append to `backend/zgrader/billing.py` (and extend its imports: `from zgrader.config import config`, `from zgrader.models import PlanEntitlement, Settings`, `from zgrader.models.checkout_attempt import ATTEMPT_ABANDONED`, `from zgrader.models.subscription import NEVER_PAID_STATUSES`):

```python
#: Stripe's Checkout session floor is 30 minutes; one more keeps clock skew
#: from turning a valid request into a rejected one.
SESSION_LIFETIME = datetime.timedelta(minutes=31)
#: A founder hold must outlive the session it holds a seat for.
HOLD_LIFETIME = datetime.timedelta(minutes=33)
_RECURRING = ("month", "year")


def founder_seats_taken(db: Session, now: datetime.datetime) -> int:
    """Founder subscriptions that ever paid, plus holds still open. A seat is
    never returned when a founder cancels: "the first N" means exactly that."""
    subscribed = (
        db.query(Subscription)
        .filter(Subscription.founder.is_(True), Subscription.status.notin_(NEVER_PAID_STATUSES))
        .count()
    )
    held = (
        db.query(CheckoutAttempt)
        .filter(
            CheckoutAttempt.founder.is_(True),
            CheckoutAttempt.state == ATTEMPT_OPEN,
            CheckoutAttempt.expires_at > now,
        )
        .count()
    )
    return subscribed + held


def founder_seats_remaining(db: Session, settings: Settings, now: datetime.datetime | None = None) -> int | None:
    """None when the offer is off, which is a different claim from zero."""
    if settings.founder_price_pence is None or settings.founder_seats is None:
        return None
    return max(0, settings.founder_seats - founder_seats_taken(db, now or _now()))


def _decide_and_insert(
    db: Session, user: User, plan: PlanEntitlement, *, terms_version: str, now: datetime.datetime
) -> CheckoutAttempt:
    """Decide founder-or-not and record the attempt, under the Settings row lock.

    Counting and inserting under one lock is what makes the last seat safe:
    a second checkout waits here until the first commits, then counts it.
    Does not commit -- reserve_attempt does, and the race test needs the gap.
    """
    settings = db.query(Settings).with_for_update().first()
    offer = (
        plan.billing_period == "year"
        and settings is not None
        and settings.founder_price_pence is not None
        and settings.founder_seats is not None
    )
    founder = bool(offer and founder_seats_taken(db, now) < settings.founder_seats)
    attempt = CheckoutAttempt(
        user_id=user.id,
        plan=plan.plan,
        amount_pence=settings.founder_price_pence if founder else plan.price_pence,
        founder=founder,
        terms_version=terms_version,
        consented_at=now,
        expires_at=now + HOLD_LIFETIME,
        state=ATTEMPT_OPEN,
    )
    db.add(attempt)
    db.flush()
    return attempt


def reserve_attempt(
    db: Session, user: User, plan: PlanEntitlement, *, terms_version: str, now: datetime.datetime
) -> CheckoutAttempt:
    attempt = _decide_and_insert(db, user, plan, terms_version=terms_version, now=now)
    db.commit()
    return attempt


def _ensure_customer(db: Session, user: User) -> str:
    if not user.stripe_customer_id:
        user.stripe_customer_id = billing_stripe.create_customer(user_id=str(user.id), email=user.email)["id"]
        db.commit()
    return user.stripe_customer_id


def _ensure_product(db: Session, plan: PlanEntitlement, business_name: str) -> str:
    if not plan.stripe_product_id:
        name = f"{business_name} — {plan.plan.capitalize()}"
        plan.stripe_product_id = billing_stripe.create_product(plan=plan.plan, name=name)["id"]
        db.commit()
    return plan.stripe_product_id


def _has_live(db: Session, user: User) -> bool:
    return (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id, Subscription.status.in_(LIVE_STATUSES))
        .first()
        is not None
    )


def create_checkout(db: Session, user: User, *, plan_name: str, terms_version: str) -> str:
    """A Checkout session URL for this user and plan. The caller has already
    checked billing is on and that the Terms version and consent are current."""
    plan = db.query(PlanEntitlement).filter(PlanEntitlement.plan == plan_name).first()
    if plan is None or plan.price_pence is None or plan.billing_period not in _RECURRING:
        raise BillingRefused(422, "That plan can't be bought here.")
    if _has_live(db, user):
        raise BillingRefused(409, "You already have a subscription — manage it from your account page.")

    now = _now()
    open_attempt = (
        db.query(CheckoutAttempt)
        .filter(
            CheckoutAttempt.user_id == user.id,
            CheckoutAttempt.state == ATTEMPT_OPEN,
            CheckoutAttempt.expires_at > now,
            CheckoutAttempt.stripe_session_url.isnot(None),
        )
        .order_by(CheckoutAttempt.created_at.desc())
        .first()
    )
    if open_attempt is not None:
        # Two tabs must be one checkout, not two subscriptions.
        return open_attempt.stripe_session_url

    try:
        customer = _ensure_customer(db, user)
        product = _ensure_product(db, plan, db.query(Settings).one().business_name)
    except Exception as exc:  # noqa: BLE001 -- any Stripe failure is a 503 to the customer
        logger.exception("could not prepare Stripe customer/product for checkout")
        raise BillingRefused(503, "Payments are unavailable right now. Please try again shortly.") from exc

    attempt = reserve_attempt(db, user, plan, terms_version=terms_version, now=now)
    try:
        session = billing_stripe.create_checkout_session(
            mode="subscription",
            customer=customer,
            client_reference_id=str(user.id),
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": "gbp",
                        "product": product,
                        "unit_amount": attempt.amount_pence,
                        "recurring": {"interval": plan.billing_period},
                    },
                }
            ],
            subscription_data={
                "metadata": {
                    "user_id": str(user.id),
                    "plan": plan.plan,
                    "founder": "true" if attempt.founder else "false",
                    "checkout_attempt_id": str(attempt.id),
                }
            },
            metadata={"checkout_attempt_id": str(attempt.id)},
            expires_at=int((now + SESSION_LIFETIME).timestamp()),
            success_url=f"{config.site_url}/account?billing=success",
            cancel_url=f"{config.site_url}/pricing",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Stripe refused to create a checkout session")
        attempt.state = ATTEMPT_ABANDONED
        db.commit()
        raise BillingRefused(503, "Payments are unavailable right now. Please try again shortly.") from exc

    attempt.stripe_session_id = session["id"]
    attempt.stripe_session_url = session["url"]
    db.commit()
    return session["url"]
```

- [ ] **Step 6: The router**

`backend/zgrader/api/routers/billing.py`:

```python
"""Stripe billing. Every route answers 404 while billing is off, so a
deployment with no Stripe account exposes nothing that half-works."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from zgrader import billing
from zgrader.api.deps import require_verified_user
from zgrader.api.ratelimit import user_rate_limit
from zgrader.api.routers.auth import CURRENT_TERMS_VERSION
from zgrader.config import config
from zgrader.db import get_db
from zgrader.models import User
from zgrader.schemas.billing import CheckoutIn, CheckoutOut

router = APIRouter(prefix="/billing", tags=["billing"])

# User-keyed: starting a checkout needs a verified account, and the account is
# what should be bounded, not the address it happens to be on.
_checkout_limit = user_rate_limit("billing_checkout", limit=10, window_seconds=3600)


def _require_billing() -> None:
    if not config.billing_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")


@router.post("/checkout", response_model=CheckoutOut, dependencies=[Depends(_checkout_limit)])
def checkout(
    payload: CheckoutIn,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> CheckoutOut:
    _require_billing()
    if payload.terms_version != CURRENT_TERMS_VERSION or not payload.immediate_start_consent:
        # The dialog was stale or the box was unticked; it re-reads and asks again.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please accept the current terms to continue.")
    try:
        url = billing.create_checkout(db, user, plan_name=payload.plan, terms_version=payload.terms_version)
    except billing.BillingRefused as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return CheckoutOut(url=url)
```

In `backend/zgrader/api/main.py`: add `billing` to the routers import and `app.include_router(billing.router)` after `catalog`.

- [ ] **Step 7: Run — expect PASS; mutation-check**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_checkout.py tests/test_rate_limit_coverage.py -v > /tmp/t5.txt 2>&1; echo $?` → `0`.
Mutations: drop `.with_for_update()` → race test fails on `is_alive`; set `extra="ignore"` → amount test fails; remove the open-attempt reuse → "same session" fails; skip marking `ATTEMPT_ABANDONED` → seat test fails.

- [ ] **Step 8: Commit**

```bash
git add backend/zgrader/billing.py backend/zgrader/schemas/billing.py backend/zgrader/api/routers/billing.py backend/zgrader/api/main.py backend/zgrader/api/routers/auth.py backend/tests/test_billing_checkout.py
git commit -m "Add /billing/checkout with race-safe founder seats and server-side amounts"
```

---

### Task 6: The webhook, its limiter, and the maintenance-Worker bypass (L2)

**Files:**
- Modify: `backend/zgrader/billing.py`, `backend/zgrader/api/routers/billing.py`, `backend/zgrader/api/ratelimit.py`, `infra/cloudflare/maintenance-worker.js`
- Create: `backend/tests/test_billing_webhook.py`, `backend/tests/test_maintenance_worker_bypass.py`

**Interfaces:**
- Consumes: `apply_subscription` (Task 4), `billing_stripe.construct_event` / `retrieve_subscription` (Task 1), `StripeEvent`, `CheckoutAttempt` (Task 2).
- Produces: `billing.HANDLED_EVENTS: frozenset[str]`; `billing.handle_event(db, event: dict) -> None` (commits); `ratelimit.stripe_webhook_rate_limit(request)`, `ratelimit.note_failed_webhook(request)`; route `POST /billing/webhook`.

- [ ] **Step 1: Write the failing webhook tests**

`backend/tests/test_billing_webhook.py`:

```python
"""POST /billing/webhook: raw-body signatures, idempotency, order, failure."""

import json

import pytest
from fastapi.testclient import TestClient

from tests.billing_fakes import FakeStripe, enable_billing, sign, subscription_obj
from zgrader.api.main import app
from zgrader.models import AuditLog, StripeEvent, Subscription, User, UserRole

client = TestClient(app)


@pytest.fixture()
def fake(monkeypatch):
    enable_billing(monkeypatch)
    return FakeStripe().install(monkeypatch)


@pytest.fixture()
def customer(db_session):
    user = User(email="hook@example.com", hashed_password="x", role=UserRole.client, is_verified=True, stripe_customer_id="cus_1")
    db_session.add(user)
    db_session.commit()
    return user


def _event(obj: dict, *, event_id="evt_1", type_="customer.subscription.updated") -> dict:
    return {"id": event_id, "object": "event", "type": type_, "data": {"object": obj}}


def _post(event: dict | None = None, *, raw: bytes | None = None, sig: str | None = None, http=client):
    payload = raw if raw is not None else json.dumps(event).encode()
    return http.post(
        "/billing/webhook",
        content=payload,
        headers={"Stripe-Signature": sig if sig is not None else sign(payload), "Content-Type": "application/json"},
    )


def test_billing_off_is_404(db_session):
    assert _post(_event({"id": "sub_1"})).status_code == 404


def test_a_bad_signature_is_400_and_records_nothing(db_session, fake, customer):
    resp = _post(_event(subscription_obj(user_id=customer.id)), sig="t=1,v1=deadbeef")
    assert resp.status_code == 400
    assert db_session.query(StripeEvent).count() == 0
    assert fake.calls == []


def test_the_signature_covers_the_raw_bytes_not_the_parsed_json(db_session, fake, customer):
    """Signed as Stripe sent it, delivered after a parse and re-dump -- the
    same JSON, different bytes. Verifying anything but the raw body would
    accept this; the check must refuse it."""
    event = _event(subscription_obj(user_id=customer.id))
    signed = json.dumps(event, indent=2).encode()
    resp = _post(raw=json.dumps(event).encode(), sig=sign(signed))
    assert resp.status_code == 400


def test_a_valid_event_mirrors_what_stripe_says_now(db_session, fake, customer):
    fake.subscriptions["sub_1"] = subscription_obj(user_id=customer.id)
    assert _post(_event({"id": "sub_1"})).status_code == 200
    db_session.expire_all()
    assert db_session.query(Subscription).one().status == "active"
    assert db_session.query(StripeEvent).one().event_id == "evt_1"


def test_the_same_event_twice_changes_things_once(db_session, fake, customer):
    fake.subscriptions["sub_1"] = subscription_obj(user_id=customer.id)
    event = _event({"id": "sub_1"})
    assert _post(event).status_code == 200
    assert _post(event).status_code == 200
    assert len(fake.called("retrieve_subscription")) == 1
    db_session.expire_all()
    assert db_session.query(AuditLog).filter(AuditLog.action == "subscription_started").count() == 1


def test_events_out_of_order_end_in_stripes_current_state(db_session, fake, customer):
    # Stripe's truth: cancelled. The stale "created" arrives last and still
    # cannot resurrect it, because the handler re-reads rather than trusting
    # the payload.
    fake.subscriptions["sub_1"] = subscription_obj(user_id=customer.id, status="canceled")
    _post(_event({"id": "sub_1"}, event_id="evt_2"))
    stale = subscription_obj(user_id=customer.id, status="active")
    _post(_event(stale, event_id="evt_1", type_="customer.subscription.created"))
    db_session.expire_all()
    assert db_session.query(Subscription).one().status == "canceled"


def test_a_failure_rolls_back_the_event_so_the_retry_does_the_work(db_session, fake, customer):
    fake.subscriptions["sub_1"] = subscription_obj(user_id=customer.id)
    fake.fail.add("retrieve_subscription")
    lenient = TestClient(app, raise_server_exceptions=False)
    assert _post(_event({"id": "sub_1"}), http=lenient).status_code == 500
    db_session.expire_all()
    assert db_session.query(StripeEvent).count() == 0

    fake.fail.clear()
    assert _post(_event({"id": "sub_1"})).status_code == 200
    db_session.expire_all()
    assert db_session.query(Subscription).count() == 1


def test_an_expired_session_releases_its_attempt(db_session, fake, customer):
    import datetime

    from zgrader.models.checkout_attempt import ATTEMPT_EXPIRED, CheckoutAttempt

    now = datetime.datetime.now(datetime.timezone.utc)
    attempt = CheckoutAttempt(
        user_id=customer.id, plan="annual", amount_pence=3000, founder=True, terms_version="2026-09",
        consented_at=now, expires_at=now + datetime.timedelta(minutes=33), stripe_session_id="cs_9",
    )
    db_session.add(attempt)
    db_session.commit()
    session_obj = {"id": "cs_9", "object": "checkout.session", "metadata": {"checkout_attempt_id": str(attempt.id)}}
    assert _post(_event(session_obj, type_="checkout.session.expired")).status_code == 200
    db_session.expire_all()
    assert db_session.get(CheckoutAttempt, attempt.id).state == ATTEMPT_EXPIRED


def test_valid_deliveries_are_never_throttled_but_forgeries_are(db_session, fake, customer):
    fake.subscriptions["sub_1"] = subscription_obj(user_id=customer.id)
    for n in range(50):
        assert _post(_event({"id": "sub_1"}, event_id=f"evt_{n}")).status_code == 200
    statuses = [_post(_event({"id": "sub_1"}), sig="t=1,v1=bad").status_code for _ in range(25)]
    assert 429 in statuses
```

- [ ] **Step 2: Write the failing bypass test**

`backend/tests/test_maintenance_worker_bypass.py`:

```python
"""The maintenance Worker must never gate Stripe's webhook.

The Worker answers before the tunnel, so with the maintenance route attached
every delivery gets its 503; Stripe retries for days, then disables the
endpoint, with nothing in origin logs because nothing reached the origin.
This ties the Worker's bypass list to the route's real path so neither end
can move alone.
"""

import re
from pathlib import Path

from zgrader.api.main import app

WORKER = Path(__file__).resolve().parents[2] / "infra" / "cloudflare" / "maintenance-worker.js"


def _bypass_prefixes() -> list[str]:
    match = re.search(r"const BYPASS_PREFIXES = \[(.*?)\];", WORKER.read_text(encoding="utf-8"), re.S)
    assert match, "BYPASS_PREFIXES not found in maintenance-worker.js"
    return re.findall(r'"([^"]+)"', match.group(1))


def test_the_webhook_route_is_bypassed():
    paths = [getattr(r, "path", "") for r in app.routes]
    webhook = next(p for p in paths if p.endswith("/billing/webhook"))
    public = "/api" + webhook  # Next.js rewrites /api/:path* to the backend
    assert any(public.startswith(prefix) for prefix in _bypass_prefixes()), (
        f"{public} is not in the maintenance Worker's BYPASS_PREFIXES"
    )
```

- [ ] **Step 3: Run — expect failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_webhook.py tests/test_maintenance_worker_bypass.py -v > /tmp/t6.txt 2>&1; echo $?; cat /tmp/t6.txt`
Expected: FAIL — route missing (`StopIteration` in the bypass test; 404/405 in the webhook tests).

- [ ] **Step 4: The failure-counting limiter**

Append to `backend/zgrader/api/ratelimit.py`:

```python
STRIPE_WEBHOOK_FAILURE_LIMIT = 20
STRIPE_WEBHOOK_FAILURE_WINDOW_SECONDS = 900


def _stripe_webhook_key(request: Request) -> str:
    return f"stripe_webhook:{client_ip(request)}"


def stripe_webhook_rate_limit(request: Request) -> None:
    """Throttle only addresses whose signatures keep failing.

    Same shape as login: valid deliveries never count, so Stripe -- which
    sends bursts from a handful of addresses -- can never be refused, while
    anyone forging signatures runs out of attempts quickly. A throttled real
    delivery would only be retried, but a limiter that can refuse the thing it
    protects is a limiter someone eventually loosens to nothing.
    """
    retry_after = _limiter.peek(
        _stripe_webhook_key(request), STRIPE_WEBHOOK_FAILURE_LIMIT, STRIPE_WEBHOOK_FAILURE_WINDOW_SECONDS
    )
    if retry_after is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many invalid requests.",
            headers={"Retry-After": str(retry_after)},
        )


def note_failed_webhook(request: Request) -> None:
    _limiter.record(_stripe_webhook_key(request), STRIPE_WEBHOOK_FAILURE_WINDOW_SECONDS)
```

- [ ] **Step 5: Event handling**

Append to `backend/zgrader/billing.py` (imports: `from sqlalchemy.dialects.postgresql import insert as pg_insert`, `from zgrader.models import StripeEvent`, `from zgrader.models.checkout_attempt import ATTEMPT_EXPIRED`):

```python
HANDLED_EVENTS = frozenset(
    {
        "checkout.session.completed",
        "checkout.session.expired",
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }
)


def _close_attempt(db: Session, session_obj: dict, state: str) -> None:
    attempt = None
    raw = (session_obj.get("metadata") or {}).get("checkout_attempt_id")
    if raw:
        try:
            attempt = db.get(CheckoutAttempt, uuid.UUID(raw))
        except ValueError:
            attempt = None
    if attempt is None and session_obj.get("id"):
        attempt = db.query(CheckoutAttempt).filter(CheckoutAttempt.stripe_session_id == session_obj["id"]).first()
    if attempt is not None and attempt.state == ATTEMPT_OPEN:
        attempt.state = state


def _apply_current(db: Session, subscription_id: str, fallback: dict) -> None:
    """Re-read the subscription rather than trusting the event: deliveries
    arrive out of order, and the newest truth is Stripe's, not the payload's.
    Only a subscription Stripe no longer has falls back to the payload -- and
    then only to record that it ended."""
    current = billing_stripe.retrieve_subscription(subscription_id)
    apply_subscription(db, current if current is not None else {**fallback, "status": "canceled"})


def handle_event(db: Session, event: dict) -> None:
    """Act on one verified event, exactly once. Commits.

    The ledger row goes in the same transaction as the effect: a duplicate
    hits the primary key and does nothing; a failure rolls both back so
    Stripe's retry does the work.
    """
    inserted = db.execute(
        pg_insert(StripeEvent)
        .values(event_id=event["id"], type=event["type"], processed_at=_now())
        .on_conflict_do_nothing(index_elements=["event_id"])
        .returning(StripeEvent.event_id)
    ).first()
    if inserted is None:
        db.rollback()
        return

    kind = event["type"]
    obj = event["data"]["object"]
    if kind == "checkout.session.completed":
        if obj.get("subscription"):
            _apply_current(db, obj["subscription"], {"id": obj["subscription"]})
        _close_attempt(db, obj, ATTEMPT_COMPLETED)
    elif kind == "checkout.session.expired":
        _close_attempt(db, obj, ATTEMPT_EXPIRED)
    elif kind.startswith("customer.subscription."):
        _apply_current(db, obj["id"], obj)
    db.commit()
```

- [ ] **Step 6: The route**

Append to `backend/zgrader/api/routers/billing.py` (imports: `from fastapi import Request`, `from starlette.concurrency import run_in_threadpool`, `from zgrader import billing_stripe`, `from zgrader.api.ratelimit import note_failed_webhook, stripe_webhook_rate_limit`):

```python
@router.post("/webhook", dependencies=[Depends(stripe_webhook_rate_limit)])
async def webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """Stripe's event callback. Public path /api/billing/webhook -- listed in
    the maintenance Worker's BYPASS_PREFIXES, which must never lose it.

    Async only so the raw body can be read before anything parses it: the
    signature covers those exact bytes. The database work runs in the
    threadpool because the session is synchronous.
    """
    _require_billing()
    payload = await request.body()
    try:
        event = billing_stripe.construct_event(payload, request.headers.get("stripe-signature", ""))
    except ValueError:
        note_failed_webhook(request)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid signature")
    try:
        await run_in_threadpool(billing.handle_event, db, event)
    except Exception:
        db.rollback()
        raise
    return {"received": True}
```

- [ ] **Step 7: The Worker bypass**

In `infra/cloudflare/maintenance-worker.js` replace the bypass constant and its comment:

```js
// Requests allowed through even while maintenance is on. Health checks and
// ACME challenges are the two that break in confusing ways if blocked.
//
// Payment callbacks must NEVER be gated. The Worker answers before the
// tunnel, so a blocked Stripe webhook gets this page's 503; Stripe retries
// for days and then disables the endpoint, and payments and entitlements
// drift apart with nothing in the origin's logs, because nothing reached the
// origin. backend/tests/test_maintenance_worker_bypass.py ties this entry to
// the route's real path. Redeploy the Worker in the Cloudflare dashboard
// whenever this list changes -- it is pasted in by hand, not deployed.
const BYPASS_PREFIXES = ["/.well-known/", "/api/billing/webhook"];
```

- [ ] **Step 8: Run — expect PASS; mutation-check**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_webhook.py tests/test_maintenance_worker_bypass.py tests/test_rate_limit_coverage.py -v > /tmp/t6.txt 2>&1; echo $?` → `0`.
Mutations: verify `json.dumps(json.loads(payload))` instead of `payload` → raw-bytes test fails; move the ledger insert into its own committed transaction → failure test fails (event recorded, retry skipped); apply `obj` instead of re-reading → out-of-order test fails; `_limiter.check` instead of `peek` → the 50-valid loop hits 429; drop the Worker entry → bypass test fails.

- [ ] **Step 9: Commit**

```bash
git add backend/zgrader/billing.py backend/zgrader/api/routers/billing.py backend/zgrader/api/ratelimit.py infra/cloudflare/maintenance-worker.js backend/tests/test_billing_webhook.py backend/tests/test_maintenance_worker_bypass.py
git commit -m "Add the Stripe webhook: raw-body signature, idempotent ledger, Worker bypass (L2)"
```

---

### Task 7: Customer Portal and the subscription read

**Files:**
- Modify: `backend/zgrader/billing.py`, `backend/zgrader/api/routers/billing.py`
- Create: `backend/tests/test_billing_portal.py`

**Interfaces:**
- Consumes: `entitlements.is_entitled` (Task 3), `BillingRefused` (Task 4), `_require_billing` (Task 5).
- Produces: `billing.current_subscription(db, user) -> Subscription | None` (live first, else most recently updated); `billing.portal_url(db, user) -> str`; routes `POST /billing/portal` → `PortalOut`, `GET /billing/subscription` → `SubscriptionOut | None`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_billing_portal.py`:

```python
"""The Portal hand-off and the account page's view of a subscription."""

import datetime

import pytest
from fastapi.testclient import TestClient

from tests.billing_fakes import FakeStripe, enable_billing
from tests.conftest import register_and_verify
from zgrader.api.main import app
from zgrader.models import Subscription, User

client = TestClient(app)
NOW = datetime.datetime.now(datetime.timezone.utc)


@pytest.fixture()
def fake(monkeypatch):
    enable_billing(monkeypatch)
    return FakeStripe().install(monkeypatch)


def _signed_in(db, email="portal@example.com", customer: str | None = None):
    headers = {"Authorization": f"Bearer {register_and_verify(client, email)}"}
    db.expire_all()
    user = db.query(User).filter_by(email=email).one()
    if customer:
        user.stripe_customer_id = customer
        db.commit()
    return headers, user


def test_every_billing_route_is_404_while_billing_is_off(db_session):
    headers, _ = _signed_in(db_session)
    assert client.post("/billing/portal", headers=headers).status_code == 404
    assert client.get("/billing/subscription", headers=headers).status_code == 404


def test_no_customer_means_nothing_to_manage(db_session, fake):
    headers, _ = _signed_in(db_session)
    assert client.post("/billing/portal", headers=headers).status_code == 409


def test_the_portal_returns_to_the_account_page(db_session, fake):
    headers, _ = _signed_in(db_session, customer="cus_9")
    resp = client.post("/billing/portal", headers=headers)
    assert resp.status_code == 200
    (call,) = fake.called("create_portal_session")
    assert call["customer"] == "cus_9" and call["return_url"].endswith("/account")


def test_no_subscription_reads_as_null(db_session, fake):
    headers, _ = _signed_in(db_session)
    resp = client.get("/billing/subscription", headers=headers)
    assert resp.status_code == 200 and resp.json() is None


def test_the_live_subscription_wins_over_a_newer_ended_one(db_session, fake):
    headers, user = _signed_in(db_session, customer="cus_9")
    db_session.add(Subscription(user_id=user.id, stripe_subscription_id="sub_live", plan="monthly", status="past_due",
                                current_period_start=NOW - datetime.timedelta(days=30)))
    db_session.commit()
    db_session.add(Subscription(user_id=user.id, stripe_subscription_id="sub_old", plan="annual", status="canceled"))
    db_session.commit()
    body = client.get("/billing/subscription", headers=headers).json()
    # Live but past its grace: shown, so the customer can fix the card, and
    # reported as not entitled, so the page can say so.
    assert (body["plan"], body["status"], body["entitled"]) == ("monthly", "past_due", False)
```

- [ ] **Step 2: Run — expect failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_portal.py -v > /tmp/t7.txt 2>&1; echo $?; cat /tmp/t7.txt` → FAIL (routes missing).

- [ ] **Step 3: Implement**

Append to `backend/zgrader/billing.py`:

```python
def current_subscription(db: Session, user: User) -> Subscription | None:
    """The subscription an account page should show: the live one if there is
    one (even past its grace -- that is exactly when the customer needs to
    see it), otherwise the most recently changed."""
    live = (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id, Subscription.status.in_(LIVE_STATUSES))
        .order_by(Subscription.updated_at.desc())
        .first()
    )
    if live is not None:
        return live
    return (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id)
        .order_by(Subscription.updated_at.desc())
        .first()
    )


def portal_url(db: Session, user: User) -> str:
    if not user.stripe_customer_id:
        raise BillingRefused(409, "There is no billing account to manage yet.")
    try:
        session = billing_stripe.create_portal_session(
            customer=user.stripe_customer_id, return_url=f"{config.site_url}/account"
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("could not open a Stripe portal session")
        raise BillingRefused(503, "Billing is unavailable right now. Please try again shortly.") from exc
    return session["url"]
```

Append to `backend/zgrader/api/routers/billing.py` (imports: `from zgrader import entitlements`, `from zgrader.api.deps import get_current_user`, `from zgrader.api.ratelimit import rate_limit`, `PortalOut, SubscriptionOut`):

```python
_portal_limit = user_rate_limit("billing_portal", limit=20, window_seconds=3600)
# Polled every 2s by /account?billing=success for up to 30s, so generous.
_subscription_read_limit = rate_limit("billing_read", limit=120, window_seconds=60)


@router.post("/portal", response_model=PortalOut, dependencies=[Depends(_portal_limit)])
def portal(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PortalOut:
    _require_billing()
    try:
        return PortalOut(url=billing.portal_url(db, user))
    except billing.BillingRefused as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


@router.get(
    "/subscription", response_model=SubscriptionOut | None, dependencies=[Depends(_subscription_read_limit)]
)
def subscription(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SubscriptionOut | None:
    _require_billing()
    row = billing.current_subscription(db, user)
    if row is None:
        return None
    return SubscriptionOut(
        plan=row.plan,
        status=row.status,
        entitled=entitlements.is_entitled(row, billing._now()),
        founder=row.founder,
        amount_pence=row.amount_pence,
        current_period_start=row.current_period_start,
        current_period_end=row.current_period_end,
        cancel_at=row.cancel_at,
    )
```

- [ ] **Step 4: Run — expect PASS; mutation-check**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_portal.py tests/test_rate_limit_coverage.py -v > /tmp/t7.txt 2>&1; echo $?` → `0`. Mutation: drop the live-first query → last test fails.

- [ ] **Step 5: Commit**

```bash
git add backend/zgrader/billing.py backend/zgrader/api/routers/billing.py backend/tests/test_billing_portal.py
git commit -m "Add the Customer Portal hand-off and GET /billing/subscription"
```

---

### Task 8: Reconciliation — worker sweep and admin button

**Files:**
- Modify: `backend/zgrader/billing.py`, `backend/zgrader/worker/main.py`, `backend/zgrader/api/routers/admin.py`
- Create: `backend/tests/test_billing_reconcile.py`

**Interfaces:**
- Consumes: `apply_subscription(..., source="reconcile")` (Task 4), `billing_stripe.list_subscriptions` / `retrieve_subscription` (Task 1), `ReconcileOut` (Task 5).
- Produces: `billing.ReconcileResult(checked: int, corrected: int)`; `billing.reconcile(db) -> ReconcileResult` (commits); `worker.main._reconcile_billing() -> bool`; route `POST /admin/billing/reconcile`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_billing_reconcile.py`:

```python
"""Reconcile: the guarantee behind the webhook. When the stack is down,
Stripe retries for days and then stops; the bypass cannot help with that,
a sweep comparing us with Stripe can."""

import datetime

import pytest
from fastapi.testclient import TestClient

from tests.billing_fakes import FakeStripe, enable_billing, subscription_obj
from tests.conftest import register_and_verify
from zgrader import billing, billing_stripe
from zgrader.api.main import app
from zgrader.db import SessionLocal
from zgrader.models import AuditLog, Subscription, User, UserRole
from zgrader.models.checkout_attempt import ATTEMPT_EXPIRED, CheckoutAttempt
from zgrader.worker import main as worker

client = TestClient(app)
NOW = datetime.datetime.now(datetime.timezone.utc)


@pytest.fixture()
def fake(monkeypatch):
    enable_billing(monkeypatch)
    return FakeStripe().install(monkeypatch)


@pytest.fixture()
def customer(db_session):
    user = User(email="rec@example.com", hashed_password="x", role=UserRole.client, is_verified=True, stripe_customer_id="cus_1")
    db_session.add(user)
    db_session.commit()
    return user


def test_a_missed_cancellation_is_corrected_and_audited(db_session, fake, customer):
    billing.apply_subscription(db_session, subscription_obj(user_id=customer.id))
    db_session.commit()
    fake.subscriptions["sub_1"] = subscription_obj(user_id=customer.id, status="canceled")

    result = billing.reconcile(db_session)

    assert (result.checked, result.corrected) == (1, 1)
    assert db_session.query(Subscription).one().status == "canceled"
    assert db_session.query(AuditLog).filter(AuditLog.action == "billing_reconciled").count() == 1


def test_a_subscription_the_webhook_never_delivered_is_created(db_session, fake, customer):
    fake.subscriptions["sub_1"] = subscription_obj(user_id=customer.id)
    assert billing.reconcile(db_session).corrected == 1
    assert db_session.query(Subscription).one().status == "active"


def test_a_live_row_stripe_no_longer_has_is_ended(db_session, fake, customer):
    billing.apply_subscription(db_session, subscription_obj(user_id=customer.id, sub_id="sub_gone"))
    db_session.commit()
    # Not in fake.subscriptions: absent from the list, and retrieve says gone.
    billing.reconcile(db_session)
    row = db_session.query(Subscription).one()
    assert row.status == "canceled"
    assert row.amount_pence == 500, "ending a row must not erase what it recorded"


def test_nothing_to_fix_corrects_nothing(db_session, fake, customer):
    obj = subscription_obj(user_id=customer.id)
    billing.apply_subscription(db_session, obj)
    db_session.commit()
    fake.subscriptions["sub_1"] = obj
    assert billing.reconcile(db_session).corrected == 0


def test_expired_holds_are_closed(db_session, fake, customer):
    attempt = CheckoutAttempt(
        user_id=customer.id, plan="annual", amount_pence=3000, founder=True, terms_version="2026-09",
        consented_at=NOW - datetime.timedelta(hours=2), expires_at=NOW - datetime.timedelta(hours=1),
    )
    db_session.add(attempt)
    db_session.commit()
    billing.reconcile(db_session)
    db_session.refresh(attempt)
    assert attempt.state == ATTEMPT_EXPIRED


def test_reconcile_does_nothing_while_billing_is_off(db_session, monkeypatch):
    called = []
    monkeypatch.setattr(billing_stripe, "list_subscriptions", lambda: called.append(1) or iter(()))
    assert billing.reconcile(db_session) == billing.ReconcileResult()
    assert called == [], "reconcile reached for Stripe on a deployment with no keys"


def test_the_worker_survives_a_stripe_outage(db_session, fake, monkeypatch):
    def boom(db):
        raise RuntimeError("Stripe unreachable")

    monkeypatch.setattr(billing, "reconcile", boom)
    assert worker._reconcile_billing() is False  # logged, not raised


def test_the_admin_button_is_operator_only(db_session, fake):
    headers = {"Authorization": f"Bearer {register_and_verify(client, 'ops@example.com')}"}
    assert client.post("/admin/billing/reconcile", headers=headers).status_code == 403
    with SessionLocal() as s:
        s.query(User).filter_by(email="ops@example.com").one().role = UserRole.operator
        s.commit()
    resp = client.post("/admin/billing/reconcile", headers=headers)
    assert resp.status_code == 200 and resp.json() == {"checked": 0, "corrected": 0}
```

- [ ] **Step 2: Run — expect failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_reconcile.py -v > /tmp/t8.txt 2>&1; echo $?; cat /tmp/t8.txt` → FAIL (`billing.reconcile` missing).

- [ ] **Step 3: Implement `reconcile`**

Append to `backend/zgrader/billing.py` (import `dataclasses`, `ATTEMPT_EXPIRED` already imported):

```python
@dataclasses.dataclass
class ReconcileResult:
    checked: int = 0
    corrected: int = 0


def _epoch(value: datetime.datetime | None) -> int | None:
    return int(value.timestamp()) if value else None


def _as_ended(row: Subscription, user: User) -> dict:
    """What a vanished subscription looks like: our own record, ended.

    Built from the row rather than blanks, so ending it keeps what it recorded
    -- amount and period -- instead of erasing them.
    """
    return {
        "id": row.stripe_subscription_id,
        "status": "canceled",
        "customer": user.stripe_customer_id,
        "metadata": {"user_id": str(row.user_id), "plan": row.plan, "founder": "true" if row.founder else "false"},
        "cancel_at": None,
        "cancel_at_period_end": False,
        "items": {
            "data": [
                {
                    "price": {"unit_amount": row.amount_pence},
                    "current_period_start": _epoch(row.current_period_start),
                    "current_period_end": _epoch(row.current_period_end),
                }
            ]
        },
    }


def reconcile(db: Session) -> ReconcileResult:
    """Bring every mirrored subscription into line with Stripe. Commits."""
    result = ReconcileResult()
    if not config.billing_enabled:
        return result

    seen: set[str] = set()
    for obj in billing_stripe.list_subscriptions():
        seen.add(obj["id"])
        result.checked += 1
        if apply_subscription(db, obj, source="reconcile"):
            result.corrected += 1

    stale = (
        db.query(Subscription)
        .filter(Subscription.status.in_(LIVE_STATUSES), Subscription.stripe_subscription_id.notin_(seen or {""}))
        .all()
    )
    for row in stale:
        result.checked += 1
        current = billing_stripe.retrieve_subscription(row.stripe_subscription_id)
        obj = current if current is not None else _as_ended(row, row.user)
        if apply_subscription(db, obj, source="reconcile"):
            result.corrected += 1

    db.query(CheckoutAttempt).filter(
        CheckoutAttempt.state == ATTEMPT_OPEN, CheckoutAttempt.expires_at <= _now()
    ).update({CheckoutAttempt.state: ATTEMPT_EXPIRED}, synchronize_session=False)
    db.commit()
    return result
```

- [ ] **Step 4: The worker sweep**

In `backend/zgrader/worker/main.py` add `from zgrader import billing` to the imports, then after `_RETENTION_SWEEP_INTERVAL_SECONDS`:

```python
#: A full pass over Stripe once a day, plus one at every boot -- which means a
#: redeploy after an outage catches up on whatever Stripe stopped retrying.
_BILLING_RECONCILE_INTERVAL_SECONDS = 24 * 3600.0
#: After a failed pass (Stripe unreachable), try again sooner than a day.
_BILLING_RECONCILE_RETRY_SECONDS = 3600.0
```

Beside `_sweep_retention`:

```python
def _reconcile_billing() -> bool:
    """Returns whether the pass completed. Never raises: this loop also runs
    scan analysis, and a Stripe outage must not stop or crash that."""
    if not config.billing_enabled:
        return True
    db = SessionLocal()
    try:
        result = billing.reconcile(db)
        log = logger.warning if result.corrected else logger.info
        log("billing reconcile: checked %d, corrected %d", result.checked, result.corrected)
        return True
    except Exception:  # noqa: BLE001
        logger.exception("billing reconcile failed; retrying in an hour")
        return False
    finally:
        db.close()
```

In `run_forever`, beside `last_sweep = 0.0`:

```python
    # Starts at 0 for the same reason as last_sweep: the first pass at boot.
    last_reconcile = 0.0
```

And inside the loop after the retention block:

```python
            if now - last_reconcile >= _BILLING_RECONCILE_INTERVAL_SECONDS:
                ok = _reconcile_billing()
                last_reconcile = (
                    now if ok else now - _BILLING_RECONCILE_INTERVAL_SECONDS + _BILLING_RECONCILE_RETRY_SECONDS
                )
```

- [ ] **Step 5: The admin button**

In `backend/zgrader/api/routers/admin.py` (imports: `import logging`, `from zgrader import billing`, `from zgrader.schemas.billing import ReconcileOut`; add `logger = logging.getLogger(__name__)` if absent):

```python
# Each press is a full pass over Stripe, so tighter than an ordinary write.
_admin_reconcile_limit = rate_limit("admin_billing_reconcile", limit=5, window_seconds=900)


@router.post("/billing/reconcile", response_model=ReconcileOut, dependencies=[Depends(_admin_reconcile_limit)])
def reconcile_billing(_operator: User = Depends(require_operator), db: Session = Depends(get_db)) -> ReconcileOut:
    """Compare every subscription with Stripe now, rather than waiting for the
    worker's daily pass -- the thing to press after an outage."""
    if not config.billing_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Billing is not enabled")
    try:
        result = billing.reconcile(db)
    except Exception as exc:  # noqa: BLE001
        logger.exception("admin reconcile failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Stripe could not be reached.") from exc
    return ReconcileOut(checked=result.checked, corrected=result.corrected)
```

- [ ] **Step 6: Run — expect PASS; mutation-check**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_reconcile.py tests/test_rate_limit_coverage.py -v > /tmp/t8.txt 2>&1; echo $?` → `0`.
Mutations: skip the stale pass → "no longer has" fails; build `_as_ended` without items → the amount assertion fails; remove the `try/except` in `_reconcile_billing` → worker test raises.

- [ ] **Step 7: Commit**

```bash
git add backend/zgrader/billing.py backend/zgrader/worker/main.py backend/zgrader/api/routers/admin.py backend/tests/test_billing_reconcile.py
git commit -m "Reconcile subscriptions against Stripe daily, at boot, and on demand"
```

---

### Task 9: Account deletion cancels billing first

**Files:**
- Modify: `backend/zgrader/api/routers/auth.py`
- Create: `backend/tests/test_billing_account_deletion.py`

**Interfaces:**
- Consumes: `billing_stripe.delete_customer` (Task 1), `config.billing_enabled`.
- Produces: `DELETE /auth/me` answers **503** and deletes nothing when a Stripe customer exists and cannot be deleted.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_billing_account_deletion.py`:

```python
"""Closing an account must stop the billing before it removes the account.

Of the two orders that can fail halfway, only Stripe-first is safe: the other
leaves a card being charged with no account behind it and nobody to ask.
"""

import pytest
from fastapi.testclient import TestClient

from tests.billing_fakes import FakeStripe, enable_billing
from tests.conftest import register_and_verify
from zgrader import billing_stripe
from zgrader.api.main import app
from zgrader.db import SessionLocal
from zgrader.models import User

client = TestClient(app)
EMAIL = "leaving@example.com"


@pytest.fixture()
def fake(monkeypatch):
    enable_billing(monkeypatch)
    return FakeStripe().install(monkeypatch)


def _headers_with_customer(customer: str | None):
    headers = {"Authorization": f"Bearer {register_and_verify(client, EMAIL)}"}
    if customer:
        with SessionLocal() as s:
            s.query(User).filter_by(email=EMAIL).one().stripe_customer_id = customer
            s.commit()
    return headers


def _exists() -> bool:
    with SessionLocal() as s:
        return s.query(User).filter_by(email=EMAIL).count() == 1


def test_no_customer_deletes_without_calling_stripe(db_session, fake):
    headers = _headers_with_customer(None)
    assert client.delete("/auth/me", headers=headers).status_code == 204
    assert fake.called("delete_customer") == [] and not _exists()


def test_stripe_is_called_before_the_account_is_gone(db_session, fake, monkeypatch):
    headers = _headers_with_customer("cus_leaving")
    seen = []

    def delete_customer(customer_id):
        seen.append((customer_id, _exists()))

    monkeypatch.setattr(billing_stripe, "delete_customer", delete_customer)
    assert client.delete("/auth/me", headers=headers).status_code == 204
    assert seen == [("cus_leaving", True)]
    assert not _exists()


def test_a_stripe_failure_deletes_nothing(db_session, fake):
    headers = _headers_with_customer("cus_leaving")
    fake.fail.add("delete_customer")
    resp = client.delete("/auth/me", headers=headers)
    assert resp.status_code == 503
    assert "nothing has been deleted" in resp.json()["detail"]
    assert _exists()


def test_a_customer_with_billing_switched_off_is_refused(db_session):
    """Keys removed after someone subscribed: we cannot reach Stripe to stop
    the charges, so we must not remove the account that explains them."""
    headers = _headers_with_customer("cus_leaving")
    assert client.delete("/auth/me", headers=headers).status_code == 503
    assert _exists()
```

- [ ] **Step 2: Run — expect failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_account_deletion.py -v > /tmp/t9.txt 2>&1; echo $?; cat /tmp/t9.txt` → the three Stripe tests FAIL (no call is made; 204 instead of 503).

- [ ] **Step 3: Implement**

In `backend/zgrader/api/routers/auth.py`: add `import logging` and `from zgrader import billing_stripe` to the imports and `logger = logging.getLogger(__name__)` below them if the module has none. In `delete_account`, directly after the operator check and before `codes = ...`:

```python
    # Stop the billing before removing the account. Deleting the Stripe
    # customer cancels its subscriptions immediately. If that cannot happen --
    # Stripe unreachable, or billing switched off since this person
    # subscribed -- refuse outright: an account deleted while its card is
    # still being charged is the one outcome here nobody can fix afterwards.
    if user.stripe_customer_id:
        refused = HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "We couldn't cancel your subscription with our payment provider, so nothing has been "
            "deleted. Please try again in a few minutes.",
        )
        if not config.billing_enabled:
            raise refused
        try:
            billing_stripe.delete_customer(user.stripe_customer_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("could not delete Stripe customer during account deletion")
            raise refused from exc
```

- [ ] **Step 4: Run — expect PASS; mutation-check**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_account_deletion.py tests/test_security_controls.py -v > /tmp/t9.txt 2>&1; echo $?` → `0`.
Mutations: move the block after `db.commit()` → the ordering test sees `False`; swallow the exception → failure test deletes the user.

- [ ] **Step 5: Commit**

```bash
git add backend/zgrader/api/routers/auth.py backend/tests/test_billing_account_deletion.py
git commit -m "Cancel billing before closing an account, and refuse if it cannot be cancelled"
```

---

### Task 10: Catalog and operator lookup fields

**Files:**
- Modify: `backend/zgrader/schemas/catalog.py`, `backend/zgrader/api/routers/catalog.py`, `backend/zgrader/schemas/admin.py`, `backend/zgrader/api/routers/admin.py`
- Create: `backend/tests/test_billing_catalog_admin.py`

**Interfaces:**
- Consumes: `billing.founder_seats_remaining`, `billing.current_subscription` (Tasks 5, 7), `CURRENT_TERMS_VERSION`.
- Produces: `PricingOut.billing_enabled: bool`, `PricingOut.founder_seats_remaining: int | None`, `PricingOut.terms_version: str`; `UserQuotaOut.subscription_status: str | None`, `UserQuotaOut.founder: bool`, `UserQuotaOut.cancel_at: datetime | None`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_billing_catalog_admin.py`:

```python
"""What the shopfront and the operator's lookup learn about billing."""

from fastapi.testclient import TestClient

from tests.billing_fakes import enable_billing
from tests.conftest import register_and_verify
from zgrader.api.main import app
from zgrader.api.routers.auth import CURRENT_TERMS_VERSION
from zgrader.db import SessionLocal
from zgrader.models import Settings, Subscription, User, UserRole

client = TestClient(app)


def test_pricing_says_billing_is_off_by_default(db_session):
    body = client.get("/catalog/pricing").json()
    assert body["billing_enabled"] is False
    assert body["terms_version"] == CURRENT_TERMS_VERSION


def test_founder_seats_remaining_counts_founders(db_session, monkeypatch):
    enable_billing(monkeypatch)
    seats = db_session.query(Settings).one().founder_seats
    user = User(email="f@example.com", hashed_password="x", role=UserRole.client)
    db_session.add(user)
    db_session.flush()
    db_session.add(Subscription(user_id=user.id, stripe_subscription_id="sub_f", plan="annual", status="active", founder=True))
    db_session.commit()
    body = client.get("/catalog/pricing").json()
    assert body["billing_enabled"] is True
    assert body["founder_seats_remaining"] == seats - 1


def test_founder_seats_remaining_is_null_when_the_offer_is_off(db_session):
    db_session.query(Settings).one().founder_price_pence = None
    db_session.commit()
    assert client.get("/catalog/pricing").json()["founder_seats_remaining"] is None


def test_the_operator_lookup_shows_billing_state(db_session):
    headers = {"Authorization": f"Bearer {register_and_verify(client, 'op2@example.com')}"}
    with SessionLocal() as s:
        s.query(User).filter_by(email="op2@example.com").one().role = UserRole.operator
        customer = User(email="sub@example.com", hashed_password="x", role=UserRole.client)
        s.add(customer)
        s.flush()
        s.add(Subscription(user_id=customer.id, stripe_subscription_id="sub_s", plan="monthly", status="past_due", founder=False))
        s.commit()
    (row,) = client.get("/admin/users/quota?email=sub@", headers=headers).json()
    assert (row["subscription_status"], row["founder"], row["cancel_at"]) == ("past_due", False, None)
```

- [ ] **Step 2: Run — expect failure**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_catalog_admin.py -v > /tmp/t10.txt 2>&1; echo $?; cat /tmp/t10.txt` → FAIL (`KeyError`).

- [ ] **Step 3: Implement**

`schemas/catalog.py`, append to `PricingOut`:

```python
    # Whether Subscribe can be offered. False keeps "Get in touch" on the page
    # rather than a button into a checkout this deployment cannot run.
    billing_enabled: bool
    # Seats left at the founder price; None when the offer is off. One
    # aggregate, nothing per user -- safe on an unauthenticated route.
    founder_seats_remaining: int | None
    # The Terms version the checkout confirm must echo back, so a customer
    # always accepts the version the server currently enforces.
    terms_version: str
```

`api/routers/catalog.py` (imports: `from zgrader import billing`, `from zgrader.api.routers.auth import CURRENT_TERMS_VERSION`), in `get_pricing`'s `PricingOut(...)` add:

```python
        billing_enabled=config.billing_enabled,
        founder_seats_remaining=billing.founder_seats_remaining(db, settings),
        terms_version=CURRENT_TERMS_VERSION,
```

`schemas/admin.py`, append to `UserQuotaOut`:

```python
    # The subscription the operator needs to see -- e.g. to apply the
    # subscriber discount on an in-hand order by hand. Never card data.
    subscription_status: str | None = None
    founder: bool = False
    cancel_at: datetime.datetime | None = None
```

`api/routers/admin.py`, in `_quota_out` (import `billing` already added in Task 8):

```python
    sub = billing.current_subscription(db, user)
    return UserQuotaOut(
        user_id=user.id,
        email=user.email,
        plan=quota.plan,
        unlimited=quota.unlimited,
        limit=quota.limit,
        used=quota.used,
        remaining=quota.remaining,
        resets_at=quota.resets_at,
        subscription_status=sub.status if sub else None,
        founder=bool(sub and sub.founder),
        cancel_at=sub.cancel_at if sub else None,
    )
```

- [ ] **Step 4: Run — expect PASS; then the whole backend suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_catalog_admin.py -v > /tmp/t10.txt 2>&1; echo $?` → `0`.
Run: `./.venv/Scripts/python.exe -m pytest -q > /tmp/full.txt 2>&1; echo $?` → `0`. Read the summary line; confirm the `test_backup_script.py` tests ran (not skipped) — skipped means you are not in Git Bash.

- [ ] **Step 5: Commit**

```bash
git add backend/zgrader/schemas/catalog.py backend/zgrader/api/routers/catalog.py backend/zgrader/schemas/admin.py backend/zgrader/api/routers/admin.py backend/tests/test_billing_catalog_admin.py
git commit -m "Publish billing availability, founder seats left and the Terms version; show billing to operators"
```

---

### Task 11: Frontend — Subscribe on `/pricing`

**Files:**
- Modify: `frontend/lib/api.ts`, `frontend/lib/use-pricing.ts`, `frontend/app/pricing/pricing-client.tsx`, `frontend/lib/i18n/en.ts`, `frontend/lib/i18n/es.ts`
- Create: `frontend/components/SubscribeButton.tsx`, `frontend/components/SubscribeDialog.tsx`

**Interfaces:**
- Consumes: `GET /catalog/pricing` new fields (Task 10), `POST /billing/checkout` (Task 5).
- Produces (`lib/api.ts`): `Pricing.billing_enabled`, `Pricing.founder_seats_remaining`, `Pricing.terms_version`; `BillingSubscription`; `startCheckout(token, plan, termsVersion) -> Promise<{url}>`; `openBillingPortal(token) -> Promise<{url}>`; `getBillingSubscription(token) -> Promise<BillingSubscription | null>`; `UserQuota.subscription_status | founder | cancel_at`.
- Produces (`lib/use-pricing.ts`): `PLAN_COPY`, `usePlanName(): (plan: string) => string`.

Read `node_modules/next/dist/docs/` for anything App-Router-specific before writing (frontend/AGENTS.md); nothing below needs a new Next API.

- [ ] **Step 1: API types and calls**

In `frontend/lib/api.ts`, extend `Pricing`:

```ts
  /** False on a deployment with no Stripe account: keep "Get in touch". */
  billing_enabled: boolean;
  /** Founder seats left; null when the offer is off. */
  founder_seats_remaining: number | null;
  /** The Terms version /billing/checkout requires the customer to accept. */
  terms_version: string;
```

Extend `UserQuota`:

```ts
  subscription_status: string | null;
  founder: boolean;
  cancel_at: string | null;
```

Add after `fetchPricing`:

```ts
// --- billing -----------------------------------------------------------
//
// The browser names a plan and confirms consent; it never sends an amount.
// The server reads the price from its own rows and hands back a Stripe-hosted
// page to redirect to, so no card detail ever touches this site.

export interface BillingSubscription {
  plan: string;
  status: string;
  /** False for a past-due subscription whose grace has run out. */
  entitled: boolean;
  founder: boolean;
  amount_pence: number | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at: string | null;
}

export async function startCheckout(token: string, plan: string, termsVersion: string): Promise<{ url: string }> {
  return request("/billing/checkout", {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ plan, terms_version: termsVersion, immediate_start_consent: true }),
  });
}

export async function openBillingPortal(token: string): Promise<{ url: string }> {
  return request("/billing/portal", { method: "POST", headers: authHeaders(token) });
}

/** Rejects with ApiError(404) when billing is off -- callers hide on that. */
export async function getBillingSubscription(token: string): Promise<BillingSubscription | null> {
  return request("/billing/subscription", { headers: authHeaders(token) });
}
```

- [ ] **Step 2: Share the plan names**

Move `PLAN_COPY` from `pricing-client.tsx` into `frontend/lib/use-pricing.ts` (exported, same content and comment), and add:

```ts
/** A plan's display name, from the same table the pricing page uses -- the
 *  account page names the plan too, and two spellings of one plan is the
 *  drift this file exists to prevent. An unknown slug falls back to itself. */
export function usePlanName(): (plan: string) => string {
  const t = useTranslations();
  return (plan) => {
    const copy = PLAN_COPY[plan];
    return copy ? (t.pricing[copy.nameKey as keyof typeof t.pricing] as string) : plan;
  };
}
```

In `pricing-client.tsx` import `PLAN_COPY` from `@/lib/use-pricing` and delete the local copy.

- [ ] **Step 3: Copy (English and Spanish)**

`en.ts`, inside `pricing`, after `paidNote`:

```ts
    subscribeCta: "Subscribe",
    subscribeSignIn: "Sign in to subscribe",
    subscribeVerify: "Confirm your email to subscribe",
    founderRemaining: "{remaining} of {seats} left.",
    confirmTitle: "Subscribe to {plan}",
    confirmBody:
      "{price} {period}, taken now and again at each renewal until you cancel. You can cancel any time from your account page. The exact amount is shown again on the payment page before you pay.",
    confirmTerms: "I accept the Terms & Conditions and the Refund Policy.",
    // DRAFT -- cooling-off wording pending the adviser's review (spec §13).
    // Live billing must not be switched on until this is approved or replaced,
    // together with the matching paragraph in refunds.s9Body.
    confirmImmediate:
      "Start my subscription straight away. I understand that because I get access immediately, I lose my right to cancel for a refund of a billing period once it has started.",
    confirmReadTerms: "Read the Terms",
    confirmReadRefunds: "Refund Policy",
    confirmContinue: "Continue to payment",
    confirmRedirecting: "Opening the payment page…",
    confirmCancel: "Cancel",
    checkoutFailed: "Couldn't start the payment. Please try again.",
```

`es.ts`, same place:

```ts
    subscribeCta: "Suscribirse",
    subscribeSignIn: "Inicie sesión para suscribirse",
    subscribeVerify: "Confirme su correo para suscribirse",
    founderRemaining: "Quedan {remaining} de {seats}.",
    confirmTitle: "Suscribirse a {plan}",
    confirmBody:
      "{price} {period}, que se cobra ahora y en cada renovación hasta que cancele. Puede cancelar cuando quiera desde su página de cuenta. El importe exacto se vuelve a mostrar en la página de pago antes de pagar.",
    confirmTerms: "Acepto los Términos y condiciones y la Política de reembolsos.",
    // BORRADOR -- redacción del desistimiento pendiente de revisión (spec §13).
    confirmImmediate:
      "Quiero que mi suscripción empiece de inmediato. Entiendo que, al tener acceso desde el primer momento, pierdo el derecho a cancelar con reembolso un periodo de facturación una vez iniciado.",
    confirmReadTerms: "Leer los Términos",
    confirmReadRefunds: "Política de reembolsos",
    confirmContinue: "Continuar al pago",
    confirmRedirecting: "Abriendo la página de pago…",
    confirmCancel: "Cancelar",
    checkoutFailed: "No se pudo iniciar el pago. Inténtelo de nuevo.",
```

- [ ] **Step 4: The confirm dialog**

`frontend/components/SubscribeDialog.tsx` — the same self-contained pattern as `ConfirmDialog`, with the two required boxes:

```tsx
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Checkbox } from "@heroui/react";
import Button from "@/components/Button";
import * as api from "@/lib/api";
import { useTranslations } from "@/lib/i18n/context";
import { toastError } from "@/lib/toast";
import { useMoney } from "@/lib/use-pricing";

/**
 * The last step before Stripe's payment page: what it costs, and the two
 * things the server refuses to proceed without -- acceptance of the Terms
 * version it currently enforces, and consent to start immediately. The
 * amount shown is the catalog's; the server decides the real one, and
 * Stripe's page shows it again before anyone pays.
 */
export default function SubscribeDialog({
  open,
  plan,
  planName,
  amountPence,
  termsVersion,
  token,
  onClose,
}: {
  open: boolean;
  plan: api.PricedPlan;
  planName: string;
  amountPence: number;
  termsVersion: string;
  token: string;
  onClose: () => void;
}) {
  const t = useTranslations();
  const money = useMoney();
  const [terms, setTerms] = useState(false);
  const [immediate, setImmediate] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) return;
    setTerms(false);
    setImmediate(false);
    setBusy(false);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, onClose]);

  if (!open) return null;

  const period = plan.billing_period === "year" ? t.pricing.perYear : t.pricing.perMonth;

  async function proceed() {
    setBusy(true);
    try {
      const { url } = await api.startCheckout(token, plan.plan, termsVersion);
      // A full navigation: Stripe's page is a different origin.
      window.location.href = url;
    } catch (err) {
      toastError(err instanceof Error ? err.message : t.pricing.checkoutFailed);
      setBusy(false);
    }
  }

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="subscribe-title" className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={busy ? undefined : onClose} />
      <div className="relative z-10 w-full max-w-md rounded-2xl border border-border bg-surface p-6 shadow-xl">
        <h2 id="subscribe-title" className="text-lg font-semibold text-foreground">
          {t.pricing.confirmTitle.replace("{plan}", planName)}
        </h2>
        <p className="mt-2 text-sm text-muted">
          {t.pricing.confirmBody.replace("{price}", money(amountPence)).replace("{period}", period)}
        </p>

        <div className="mt-4 flex flex-col gap-3">
          <Checkbox.Root isSelected={terms} onChange={setTerms}>
            <Checkbox.Content>
              <Checkbox.Control>
                <Checkbox.Indicator />
              </Checkbox.Control>
              <span className="text-sm">{t.pricing.confirmTerms}</span>
            </Checkbox.Content>
          </Checkbox.Root>
          <p className="text-xs text-muted">
            <Link href="/terms" target="_blank" className="-my-2 inline-block py-2 text-accent underline-offset-2 hover:underline">
              {t.pricing.confirmReadTerms}
            </Link>
            {" · "}
            <Link href="/refunds" target="_blank" className="-my-2 inline-block py-2 text-accent underline-offset-2 hover:underline">
              {t.pricing.confirmReadRefunds}
            </Link>
          </p>
          <Checkbox.Root isSelected={immediate} onChange={setImmediate}>
            <Checkbox.Content>
              <Checkbox.Control>
                <Checkbox.Indicator />
              </Checkbox.Control>
              <span className="text-sm">{t.pricing.confirmImmediate}</span>
            </Checkbox.Content>
          </Checkbox.Root>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="outline" onPress={onClose} isDisabled={busy}>
            {t.pricing.confirmCancel}
          </Button>
          <Button variant="primary" onPress={proceed} isDisabled={busy || !terms || !immediate}>
            {busy ? t.pricing.confirmRedirecting : t.pricing.confirmContinue}
          </Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: The button**

`frontend/components/SubscribeButton.tsx`:

```tsx
"use client";

import Link from "next/link";
import { useState } from "react";
import SubscribeDialog from "@/components/SubscribeDialog";
import type * as api from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useTranslations } from "@/lib/i18n/context";

const CTA = "inline-flex min-h-11 items-center text-sm font-semibold text-accent link-accent-hover hover:underline";

/**
 * Subscribe, pointed at what the visitor actually needs first. Signed out it
 * is sign-in (no return path yet -- /login has no ?next=); unverified it is
 * the account page, because checkout refuses an unconfirmed address exactly
 * as submitting does.
 */
export default function SubscribeButton({
  plan,
  planName,
  amountPence,
  termsVersion,
}: {
  plan: api.PricedPlan;
  planName: string;
  amountPence: number;
  termsVersion: string;
}) {
  const { user, token } = useAuth();
  const t = useTranslations();
  const [open, setOpen] = useState(false);

  if (!user || !token) return <Link href="/login" className={CTA}>{t.pricing.subscribeSignIn}</Link>;
  if (!user.is_verified) return <Link href="/account" className={CTA}>{t.pricing.subscribeVerify}</Link>;

  return (
    <>
      <button type="button" className={CTA} onClick={() => setOpen(true)}>
        {t.pricing.subscribeCta}
      </button>
      <SubscribeDialog
        open={open}
        plan={plan}
        planName={planName}
        amountPence={amountPence}
        termsVersion={termsVersion}
        token={token}
        onClose={() => setOpen(false)}
      />
    </>
  );
}
```

- [ ] **Step 6: Wire `/pricing`**

In `pricing-client.tsx`, import `SubscribeButton`. Inside the plan map, before `return`, compute what an annual buyer would be quoted:

```tsx
              const founderQuote =
                plan.billing_period === "year" &&
                pricing.founder_price_pence != null &&
                (pricing.founder_seats_remaining ?? 0) > 0
                  ? pricing.founder_price_pence
                  : null;
              const sellable =
                pricing.billing_enabled && (plan.billing_period === "month" || plan.billing_period === "year");
```

Replace the paid branch of the CTA (`<Link href="/contact">…paidCta…</Link>`) with:

```tsx
                      ) : sellable ? (
                        <SubscribeButton
                          plan={plan}
                          planName={name}
                          amountPence={founderQuote ?? plan.price_pence!}
                          termsVersion={pricing.terms_version}
                        />
                      ) : (
                        <Link href="/contact" className="inline-flex min-h-11 items-center text-sm font-semibold text-accent link-accent-hover hover:underline">
                          {t.pricing.paidCta}
                        </Link>
                      )}
```

Replace the unconditional `paidNote` paragraph (and its comment) with:

```tsx
        {/* Only while nothing takes payments: say how a paid tier starts
            rather than letting someone find out at a dead end. */}
        {pricing !== null && !pricing.billing_enabled && (
          <p className="mt-3 text-sm text-muted">{t.pricing.paidNote}</p>
        )}
```

Replace the founder `<li>` so it disappears at zero and counts down while billing is on:

```tsx
            {pricing.founder_price_pence != null &&
              pricing.founder_seats != null &&
              pricing.founder_seats_remaining !== 0 && (
                <li>
                  {t.pricing.founder
                    .replace("{seats}", String(pricing.founder_seats))
                    .replace("{price}", money(pricing.founder_price_pence))}
                  {pricing.billing_enabled && pricing.founder_seats_remaining != null && (
                    <>
                      {" "}
                      {t.pricing.founderRemaining
                        .replace("{remaining}", String(pricing.founder_seats_remaining))
                        .replace("{seats}", String(pricing.founder_seats))}
                    </>
                  )}
                </li>
              )}
```

- [ ] **Step 7: Typecheck and build**

Run: `cd frontend && npx tsc --noEmit && npx next build` → both succeed (tsc also proves `es.ts` has every new key).

- [ ] **Step 8: Browser-verify against a local backend on `zgrader_test`**

Start the backend from Git Bash in `backend/` with `ZGRADER_DATABASE_URL=postgresql+psycopg://zgrader:zgrader@localhost:5432/zgrader_test`, **dummy** keys `ZGRADER_STRIPE_SECRET_KEY=sk_test_dummy ZGRADER_STRIPE_WEBHOOK_SECRET=whsec_dummy`, and `./.venv/Scripts/python.exe -m uvicorn zgrader.api.main:app --port 8000`; start the frontend with the Browser pane's `preview_start` (add a `.claude/launch.json` entry for `npm run dev` in `frontend/` if none exists). First confirm `Get-NetTCPConnection -LocalPort 5432 -State Listen` — if it names `ssh.exe`, the database name must still be `zgrader_test`.

Check, and screenshot each:
- Keys unset → `/pricing` shows "Get in touch" on monthly/annual and the "arranged directly" note.
- Dummy keys, signed out → "Sign in to subscribe"; signed in unverified → "Confirm your email to subscribe"; verified → **Subscribe** opens the dialog; Continue stays disabled until both boxes are ticked; Escape and the overlay close it; Continue with dummy keys shows the `checkoutFailed`-style toast from the 503 (proves the round trip without a real Stripe account).
- Annual shows the founder price in the dialog and "N of M left" in the extras list.
- Both languages; `document.body.scrollWidth === window.innerWidth` at 320/375/768/1024/1280 with the dialog open and closed; every `a, button` and checkbox label ≥ 24×24 using the union-of-descendants method in `frontend/AGENTS.md`.

- [ ] **Step 9: Commit**

```bash
git add frontend/lib/api.ts frontend/lib/use-pricing.ts frontend/app/pricing/pricing-client.tsx frontend/components/SubscribeButton.tsx frontend/components/SubscribeDialog.tsx frontend/lib/i18n/en.ts frontend/lib/i18n/es.ts
git commit -m "Offer Subscribe on /pricing behind a Terms and consent confirm"
```

---

### Task 12: Frontend — the account billing card and the operator's view

**Files:**
- Create: `frontend/components/BillingCard.tsx`
- Modify: `frontend/app/account/page.tsx`, `frontend/app/admin/settings/page.tsx`, `frontend/lib/i18n/en.ts`, `frontend/lib/i18n/es.ts`

**Interfaces:**
- Consumes: `getBillingSubscription`, `openBillingPortal`, `ApiError` (whose field is `status`), `BillingSubscription`, `UserQuota` billing fields (Task 11); `usePlanName`, `useMoney`, `usePricing` (`lib/use-pricing.ts`); `useLocale` (`lib/i18n/context`).
- Produces: `<BillingCard />` — renders nothing while billing is off (the endpoint answers 404).

- [ ] **Step 1: Copy (English and Spanish)**

`en.ts`, inside `account`, after `deleteFailed`:

```ts
    billingTitle: "Subscription",
    billingNone: "You're on the free plan.",
    billingSeePlans: "See plans",
    billingPlan: "{plan} — {price} {period}",
    billingFounder: "Founder price",
    billingRenews: "Renews on {date}.",
    billingEnds: "Ends on {date}. You keep access until then.",
    billingPastDue: "Your last payment didn't go through. Update your card to keep your subscription.",
    billingManage: "Manage billing",
    billingOpening: "Opening…",
    billingConfirming: "Confirming your subscription…",
    billingSlow:
      "This is taking longer than usual — it will appear here shortly. You don't need to pay again.",
    billingFailed: "Couldn't open billing.",
```

And replace `deleteConfirmBody` (closing the account now cancels billing, and says so before the button is pressed rather than after):

```ts
    deleteConfirmBody:
      "Everything is removed immediately and permanently. There is no way to recover it. If you have a subscription, it is cancelled at the same moment, with no refund for the period in progress.",
```

`es.ts`, same places:

```ts
    billingTitle: "Suscripción",
    billingNone: "Está en el plan gratuito.",
    billingSeePlans: "Ver planes",
    billingPlan: "{plan} — {price} {period}",
    billingFounder: "Precio fundador",
    billingRenews: "Se renueva el {date}.",
    billingEnds: "Termina el {date}. Mantiene el acceso hasta entonces.",
    billingPastDue:
      "Su último pago no se completó. Actualice su tarjeta para mantener la suscripción.",
    billingManage: "Gestionar facturación",
    billingOpening: "Abriendo…",
    billingConfirming: "Confirmando su suscripción…",
    billingSlow:
      "Está tardando más de lo habitual: aparecerá aquí en breve. No necesita volver a pagar.",
    billingFailed: "No se pudo abrir la facturación.",
```

```ts
    deleteConfirmBody:
      "Todo se elimina de inmediato y de forma permanente. No hay manera de recuperarlo. Si tiene una suscripción, se cancela en ese mismo momento, sin reembolso del periodo en curso.",
```

- [ ] **Step 2: The card**

`frontend/components/BillingCard.tsx`:

```tsx
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card } from "@heroui/react";
import Button from "@/components/Button";
import * as api from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useLocale, useTranslations } from "@/lib/i18n/context";
import { toastError } from "@/lib/toast";
import { useMoney, usePlanName, usePricing } from "@/lib/use-pricing";

/** Mirrors LIVE_STATUSES in backend/zgrader/models/subscription.py. */
const LIVE = new Set(["active", "trialing", "past_due"]);
/** 15 polls at 2s: the "30 seconds" the spec gives the webhook to arrive. */
const POLL_ATTEMPTS = 15;
const POLL_INTERVAL_MS = 2000;

/**
 * The account's subscription, read from our own database -- never inferred
 * from having landed on ?billing=success. Arriving back from Stripe polls
 * until the webhook has recorded the subscription, and if it has not after
 * thirty seconds says so plainly, including that paying again is not the fix.
 *
 * Renders nothing while billing is off: the endpoint answers 404 then.
 */
export default function BillingCard() {
  const { token } = useAuth();
  const t = useTranslations();
  const { locale } = useLocale();
  const money = useMoney();
  const planName = usePlanName();
  const pricing = usePricing();

  const [ready, setReady] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [sub, setSub] = useState<api.BillingSubscription | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [slow, setSlow] = useState(false);
  const [opening, setOpening] = useState(false);

  useEffect(() => {
    if (!token) return;
    const params = new URLSearchParams(window.location.search);
    const returning = params.get("billing") === "success";
    // Strip it so a refresh does not replay the confirming state.
    if (returning) window.history.replaceState(null, "", window.location.pathname);

    let cancelled = false;
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const current = await api.getBillingSubscription(token!);
        if (cancelled) return;
        setSub(current);
        setReady(true);
        if (returning && !(current && LIVE.has(current.status))) {
          attempts += 1;
          if (attempts < POLL_ATTEMPTS) {
            setConfirming(true);
            timer = setTimeout(poll, POLL_INTERVAL_MS);
            return;
          }
          setSlow(true);
        }
        setConfirming(false);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof api.ApiError && err.status === 404) setHidden(true);
        setReady(true);
      }
    }

    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [token]);

  if (!ready || hidden || !token) return null;

  const formatDate = (iso: string) =>
    // The app's locale, never the browser's -- see frontend/AGENTS.md.
    new Date(iso).toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric" });
  const billingPeriod = pricing?.plans.find((p) => p.plan === sub?.plan)?.billing_period;
  const periodLabel =
    billingPeriod === "year" ? t.pricing.perYear : billingPeriod === "month" ? t.pricing.perMonth : "";

  async function manage() {
    setOpening(true);
    try {
      const { url } = await api.openBillingPortal(token!);
      window.location.href = url;
    } catch (err) {
      toastError(err instanceof Error ? err.message : t.account.billingFailed);
      setOpening(false);
    }
  }

  const live = sub !== null && LIVE.has(sub.status);

  return (
    <Card>
      <Card.Header>
        <Card.Title>{t.account.billingTitle}</Card.Title>
      </Card.Header>
      <Card.Content className="flex flex-col gap-2">
        {confirming && (
          <p className="text-sm text-muted" aria-live="polite">
            {t.account.billingConfirming}
          </p>
        )}
        {slow && <p className="text-sm text-muted">{t.account.billingSlow}</p>}

        {live ? (
          <>
            <p className="text-sm font-medium text-foreground">
              {t.account.billingPlan
                .replace("{plan}", planName(sub.plan))
                .replace("{price}", sub.amount_pence != null ? money(sub.amount_pence) : "")
                .replace("{period}", periodLabel)}
              {sub.founder && (
                <span className="ml-2 rounded-full border border-border px-2 py-0.5 text-xs text-muted">
                  {t.account.billingFounder}
                </span>
              )}
            </p>
            {sub.cancel_at ? (
              <p className="text-sm text-muted">{t.account.billingEnds.replace("{date}", formatDate(sub.cancel_at))}</p>
            ) : sub.current_period_end ? (
              <p className="text-sm text-muted">
                {t.account.billingRenews.replace("{date}", formatDate(sub.current_period_end))}
              </p>
            ) : null}
            {sub.status === "past_due" && (
              <p className="rounded-lg border border-dashed border-border p-3 text-sm text-foreground">
                {t.account.billingPastDue}
              </p>
            )}
            <div className="mt-2">
              <Button variant="secondary" isDisabled={opening} onPress={manage}>
                {opening ? t.account.billingOpening : t.account.billingManage}
              </Button>
            </div>
          </>
        ) : (
          !confirming && (
            <p className="text-sm text-muted">
              {t.account.billingNone}{" "}
              <Link href="/pricing" className="-my-2 inline-block py-2 font-semibold text-accent underline-offset-2 hover:underline">
                {t.account.billingSeePlans}
              </Link>
            </p>
          )
        )}
      </Card.Content>
    </Card>
  );
}
```

- [ ] **Step 3: Place it on the account page**

In `frontend/app/account/page.tsx`: `import BillingCard from "@/components/BillingCard";` and render `<BillingCard />` directly after the first `</Card>` (the profile card), before "Change password".

- [ ] **Step 4: The operator's lookup**

In `frontend/app/admin/settings/page.tsx`, inside the result row's `text-xs text-muted` div, after the quota text expression, append (the admin panel is English-only — backlog N1):

```tsx
              {row.subscription_status &&
                ` · subscription ${row.subscription_status}` +
                  (row.founder ? " (founder)" : "") +
                  (row.cancel_at ? `, ends ${new Date(row.cancel_at).toLocaleDateString(locale)}` : "")}
```

- [ ] **Step 5: Typecheck and build**

Run: `cd frontend && npx tsc --noEmit && npx next build` → both succeed.

- [ ] **Step 6: Browser-verify each state**

Same local setup as Task 11 Step 8 (backend on `zgrader_test`, dummy keys). Produce each state by inserting a row with the test database's own session — from Git Bash in `backend/`:

```bash
ZGRADER_DATABASE_URL=postgresql+psycopg://zgrader:zgrader@localhost:5432/zgrader_test ./.venv/Scripts/python.exe - <<'EOF'
import datetime
from zgrader.db import SessionLocal
from zgrader.models import Subscription, User
now = datetime.datetime.now(datetime.timezone.utc)
with SessionLocal() as s:
    u = s.query(User).filter_by(email="YOUR-TEST-ACCOUNT@example.com").one()
    u.stripe_customer_id = u.stripe_customer_id or "cus_local_demo"
    s.query(Subscription).filter_by(user_id=u.id).delete()
    s.add(Subscription(user_id=u.id, stripe_subscription_id="sub_local_demo", plan="annual", status="active",
                       founder=True, amount_pence=3000, current_period_start=now,
                       current_period_end=now + datetime.timedelta(days=365)))
    s.commit()
EOF
```

Vary `status` / `cancel_at` / `founder` and reload `/account` for: **none** (delete the row), **active**, **founder**, **cancelling** (`cancel_at` set), **past due**. For **confirming**, delete the row and open `/account?billing=success` — the confirming line shows, then after ~30s the "longer than usual" line, and the query string is gone from the address bar. With keys unset the card is absent. Screenshot each; both languages (the date must read in Spanish on the Spanish page); overflow and target-size sweep at the five widths. In the admin lookup, the row reads `· subscription active (founder)`.

- [ ] **Step 7: Commit**

```bash
git add frontend/components/BillingCard.tsx frontend/app/account/page.tsx frontend/app/admin/settings/page.tsx frontend/lib/i18n/en.ts frontend/lib/i18n/es.ts
git commit -m "Show the subscription on the account page and to operators"
```

---

### Task 13: The published promises — Terms, Privacy, Refund Policy

**Files:**
- Modify: `frontend/lib/i18n/en.ts`, `frontend/lib/i18n/es.ts`, `frontend/app/refunds/refunds-client.tsx`, `backend/zgrader/entitlements.py` (comment only)
- Create: `backend/tests/test_billing_published_promises.py`

**Interfaces:**
- Consumes: `entitlements.PAST_DUE_GRACE` (Task 3) — quoted on the Refund Policy, so the two are tied by a test.
- Produces: `refunds.s9Title` / `refunds.s9Body` in both dictionaries.

Every change below is in the same PR as the checkout (the published-promise rule). Replace each string **whole** — do not splice — and read both languages back rendered in the browser afterwards; tooling has mangled accents and em dashes before.

- [ ] **Step 1: Write the failing cross-file test**

`backend/tests/test_billing_published_promises.py`:

```python
"""A figure the Refund Policy quotes must be the figure the code enforces.

The grace period for a failed payment is a constant in entitlements.py and a
sentence on a public page. Nothing but this test keeps them in step -- the
same failure the free-allowance copy had when it promised one check while the
seed granted three.
"""

from pathlib import Path

from zgrader.entitlements import PAST_DUE_GRACE

I18N = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "i18n"


def test_the_refund_policy_quotes_the_enforced_grace_period():
    days = PAST_DUE_GRACE.days
    assert f"up to {days} days" in (I18N / "en.ts").read_text(encoding="utf-8")
    assert f"hasta {days} días" in (I18N / "es.ts").read_text(encoding="utf-8")


def test_neither_language_still_says_nothing_is_sold_here():
    for name, phrases in {
        "en.ts": ("Nothing is sold through this website", "there is no checkout"),
        "es.ts": ("Nada se compra a través de este sitio web",),
    }.items():
        text = (I18N / name).read_text(encoding="utf-8")
        for phrase in phrases:
            assert phrase not in text, f"{name} still says: {phrase!r}"
```

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_published_promises.py -v > /tmp/t13.txt 2>&1; echo $?` → FAIL on both.

- [ ] **Step 2: Tie the constant to the page**

Above `PAST_DUE_GRACE` in `backend/zgrader/entitlements.py`, add to its comment:

```python
#: A published promise: Refund Policy §9 quotes this number in both languages,
#: and tests/test_billing_published_promises.py fails if they disagree.
```

- [ ] **Step 3: English**

In `en.ts`, set `updatedValue: "September 2026"` in `terms`, `privacy` and `refunds`.

`terms.s7Body`:

```ts
      "The basic image analysis is free to use, subject to fair-use limits. The monthly and annual subscriptions are bought on this website: payment is taken by Stripe, our payment processor, on Stripe's own secure page, and the card details you enter there never reach us. A subscription renews automatically at the end of each period until you cancel it, which you can do at any time from your account page; it then runs to the end of the period already paid for. Other paid services — the credit pack and anything involving a physical card — are arranged with you directly, and their fees are agreed before work starts. Cancellation and refunds are covered by the Refund Policy, which forms part of these terms.",
```

`privacy.s2Body` — replace its final sentence only, which today reads *"We do not use advertising or analytics tracking, and we never see your payment card details."*, with:

```
If you subscribe, we also keep the identifiers Stripe gives your customer record and your subscription, the plan, the amount you pay, the billing dates and status, and which version of the terms you accepted and when you asked for the subscription to start straight away. We do not use advertising or analytics tracking, and we never see your payment card details.
```

`privacy.s3Body` — after *"Both are necessary to perform the service you requested."* insert:

```
The billing details above are needed to take payment for a subscription and to keep the records the law requires of a business that sells.
```

`privacy.s6Body` — before its final sentence (*"None of this can be undone, …"*) insert:

```
If you have a subscription, closing your account cancels it and deletes your customer record at Stripe at the same moment. Stripe keeps its own record of the payments themselves for as long as the law requires it to, under Stripe's own privacy policy; that record is Stripe's rather than ours, and deleting your account here cannot remove it.
```

`privacy.s7Body`:

```ts
      "Nobody, other than the service operator. We do not sell personal data and we do not share it with grading companies. The service runs on hardware the operator owns rather than at a hosting company, so your images are not sitting on someone else's cloud. Four suppliers are unavoidably involved and are named here rather than hidden behind a general clause: Cloudflare carries traffic between your browser and the service, and sees the connection and your IP address; an email provider delivers the messages we send you, and sees your address and the contents of those messages; Google, only if you choose to sign in with Google, which tells them you use this service; and Stripe, only if you subscribe, which processes the payment and sees your name, email address, card details, billing address and IP address — the card number goes to Stripe directly and never reaches us. Beyond that we disclose personal data only where we are legally required to.",
```

`refunds.s1Body`:

```ts
      "This policy covers services you pay for. The free image analysis costs nothing and so has nothing to refund — if you are on the free allowance, none of this applies to you. Subscriptions are bought on this website and are covered by section 9. Every other paid service is arranged with you directly, and its price is agreed before any work starts.",
```

After `s8Body`, add:

```ts
    s9Title: "9. Subscriptions",
    // DRAFT in part -- the sentence about starting straight away mirrors the
    // checkout consent (pricing.confirmImmediate) and awaits the adviser's
    // review (spec §13). The 21 days is PAST_DUE_GRACE in entitlements.py.
    s9Body:
      "You can cancel a subscription at any time from your account page. It then runs to the end of the period you have already paid for and is not renewed, so nothing further is charged; we do not refund part of a period that has already started. When you subscribe you ask us to give you access straight away, and you agree that this means you cannot cancel for a refund of a period once it has begun — we ask you to confirm that before you pay. Closing your account cancels your subscription at the same moment, without a refund for the period in progress. If a renewal payment fails, your subscription stays active for up to 21 days while the payment is retried; if it still cannot be taken, the subscription ends and your account returns to the free plan. Section 7 applies to subscriptions exactly as it does to everything else: if something has gone wrong on our side, we will put it right.",
```

- [ ] **Step 4: Spanish**

In `es.ts`, set `updatedValue: "Septiembre de 2026"` in `terms`, `privacy` and `refunds`.

`terms.s7Body`:

```ts
      "El análisis básico de imagen es gratuito, sujeto a límites de uso razonable. Las suscripciones mensual y anual se contratan en este sitio web: el pago lo cobra Stripe, nuestro procesador de pagos, en su propia página segura, y los datos de tarjeta que introduzca allí nunca llegan a nosotros. Una suscripción se renueva automáticamente al final de cada periodo hasta que la cancele, algo que puede hacer en cualquier momento desde su página de cuenta; después sigue vigente hasta el final del periodo ya pagado. Los demás servicios de pago — el bono de créditos y todo lo que implique una carta física — se acuerdan con usted directamente, y sus tarifas se fijan antes de iniciar el trabajo. La cancelación y los reembolsos se rigen por la Política de reembolsos, que forma parte de estos términos.",
```

`privacy.s2Body` — replace the final sentence *"No usamos publicidad ni analítica de seguimiento, y nunca vemos los datos de su tarjeta de pago."* with:

```
Si se suscribe, también conservamos los identificadores que Stripe asigna a su registro de cliente y a su suscripción, el plan, el importe que paga, las fechas y el estado de la facturación, y qué versión de los términos aceptó y cuándo pidió que la suscripción empezara de inmediato. No usamos publicidad ni analítica de seguimiento, y nunca vemos los datos de su tarjeta de pago.
```

`privacy.s3Body` — after *"Ambas cosas son necesarias para prestar el servicio que pidió."* insert:

```
Los datos de facturación anteriores son necesarios para cobrar una suscripción y para conservar los registros que la ley exige a un negocio que vende.
```

`privacy.s6Body` — before its final sentence (*"Nada de esto se puede deshacer, …"*) insert:

```
Si tiene una suscripción, cerrar su cuenta la cancela y elimina al mismo tiempo su registro de cliente en Stripe. Stripe conserva su propio registro de los pagos en sí durante el tiempo que la ley le obligue, conforme a su propia política de privacidad; ese registro es de Stripe y no nuestro, y eliminar su cuenta aquí no puede borrarlo.
```

`privacy.s7Body`:

```ts
      "Nadie, salvo el operador del servicio. No vendemos datos personales ni los compartimos con compañías de calificación. El servicio funciona en equipos propiedad del operador y no en una empresa de alojamiento, de modo que sus imágenes no están en la nube de un tercero. Hay cuatro proveedores inevitablemente implicados, y se nombran aquí en lugar de ocultarse tras una cláusula genérica: Cloudflare transporta el tráfico entre su navegador y el servicio, y ve la conexión y su dirección IP; un proveedor de correo entrega los mensajes que le enviamos, y ve su dirección y el contenido de esos mensajes; Google, solo si elige iniciar sesión con Google, lo que les indica que usa este servicio; y Stripe, solo si se suscribe, que procesa el pago y ve su nombre, su correo electrónico, los datos de su tarjeta, su dirección de facturación y su dirección IP — el número de tarjeta va directamente a Stripe y nunca llega a nosotros. Más allá de eso, solo revelamos datos personales cuando la ley nos obliga.",
```

`refunds.s1Body`:

```ts
      "Esta política cubre los servicios que usted paga. El análisis de imagen gratuito no cuesta nada y por tanto no hay nada que reembolsar — si está usando la cuota gratuita, nada de esto le afecta. Las suscripciones se contratan en este sitio web y se rigen por la sección 9. Cualquier otro servicio de pago se acuerda con usted directamente, y su precio se fija antes de iniciar cualquier trabajo.",
```

After `s8Body`:

```ts
    s9Title: "9. Suscripciones",
    // BORRADOR en parte -- ver la nota de en.ts.
    s9Body:
      "Puede cancelar una suscripción en cualquier momento desde su página de cuenta. Después sigue vigente hasta el final del periodo que ya ha pagado y no se renueva, así que no se cobra nada más; no reembolsamos parte de un periodo ya iniciado. Al suscribirse nos pide que le demos acceso de inmediato, y acepta que eso significa que no puede cancelar con reembolso un periodo una vez iniciado — se lo pedimos confirmar antes de pagar. Cerrar su cuenta cancela su suscripción en ese mismo momento, sin reembolso del periodo en curso. Si falla el pago de una renovación, su suscripción sigue activa hasta 21 días mientras se reintenta el cobro; si aun así no se puede cobrar, la suscripción termina y su cuenta vuelve al plan gratuito. La sección 7 se aplica a las suscripciones exactamente igual que a todo lo demás: si algo ha salido mal por nuestra parte, lo subsanaremos.",
```

- [ ] **Step 5: Render section 9**

In `frontend/app/refunds/refunds-client.tsx`, add to the `sections` array after the `s8` entry:

```tsx
    { title: t.refunds.s9Title, body: t.refunds.s9Body },
```

- [ ] **Step 6: Verify**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_billing_published_promises.py -v > /tmp/t13.txt 2>&1; echo $?` → `0` (mutation: change 21 to 20 in one language → fails).
Run: `cd frontend && npx tsc --noEmit && npx next build` → succeed.
In the browser: `/terms`, `/privacy`, `/refunds` in both languages — section 9 renders, every accent and em dash is intact, the dates read September 2026 / Septiembre de 2026, no horizontal scroll at the five widths.

- [ ] **Step 7: Commit**

```bash
git add frontend/lib/i18n/en.ts frontend/lib/i18n/es.ts frontend/app/refunds/refunds-client.tsx backend/zgrader/entitlements.py backend/tests/test_billing_published_promises.py
git commit -m "Terms, Privacy and Refund Policy: subscriptions are sold here, through Stripe"
```

---

### Task 14: Write down what this made true — AGENTS.md and the go-live checklist

**Files:**
- Modify: `AGENTS.md`, `docs/deployment.md`
- Modify (local only, gitignored — never commit): `docs/superpowers/plans/2026-09-06-remediation-backlog.md`

**Interfaces:** none — documentation of Tasks 1–13.

- [ ] **Step 1: AGENTS.md — remove the entry that is no longer true**

In "Known-open, deliberately", delete the whole bullet beginning **"Nothing takes payment, and no account can be on a paid plan."** Update the sentence after the list that begins "Five entries left this list…" to "Six entries…" and add one line to it: *the sixth was that nothing took payment; subscriptions are now sold through Stripe — see the billing invariant above.*

- [ ] **Step 2: AGENTS.md — add the invariant**

Add under "Invariants", after the "Every published price is a row…" paragraph:

```markdown
**Stripe is the authority on payment; `subscriptions` is its mirror, and one function writes it.**
`billing.apply_subscription` is the only writer — the webhook, the worker's reconcile sweep and
`POST /admin/billing/reconcile` all end there. It re-reads the subscription from Stripe rather
than trusting an event payload (deliveries arrive out of order), and it checks the metadata's
user against `users.stripe_customer_id` before writing anything. Access is **never** granted
because a browser reached the success page; `/account?billing=success` polls our own database.

Prices stay single-sourced: checkout sends `plan_entitlements.price_pence` (or the founder price)
inline, so no Stripe Price is ever authored and the admin panel remains the only place a price
changes. The browser names a plan and nothing else — `CheckoutIn` forbids extra fields.

**The webhook is the fast path and reconciliation is the guarantee.** `/api/billing/webhook` is in
the maintenance Worker's `BYPASS_PREFIXES` (a test ties the two strings), because a gated webhook
gets a 503 from the edge that never appears in origin logs. But the bypass cannot help when the
stack itself is down — Stripe retries for days and then stops — so the worker reconciles at boot
and daily, and every correction lands in the audit log as `billing_reconciled`.

Signature verification runs on the **raw body**, before anything parses it; the webhook endpoint is
`async` for that reason alone. `stripe_events` is written in the same transaction as the event's
effect, so a duplicate does nothing and a failure is retried for real. Only
`zgrader/billing_stripe.py` imports `stripe`, and `STRIPE_API_VERSION` fails a test when an SDK
upgrade changes the API version under it.

A quota window belongs to the plan it was counted under: `get_quota` resets it when
`users.quota_plan` no longer matches, which covers a grace period expiring with nothing written.
`past_due` stays entitled for `PAST_DUE_GRACE` from `current_period_start` — the failed renewal,
not the period end, which is a whole period later — and Refund Policy §9 quotes that number.
```

- [ ] **Step 3: docs/deployment.md — "Taking payments"**

Insert before `## Still open`:

```markdown
## Taking payments

Billing is off until both `ZGRADER_STRIPE_SECRET_KEY` and `ZGRADER_STRIPE_WEBHOOK_SECRET` are set;
until then `/pricing` says "Get in touch" and every `/billing` route answers 404. Do the steps in
this order, **in Stripe test mode first**, end to end, before any live key goes in.

1. **The account.** Onboard as a Gibraltar business (registered entity, local address, Gibraltar
   bank account). Get written answers on the cooling-off consent wording (the draft is in
   `pricing.confirmImmediate` and Refund Policy §9) and on VAT for UK/EU consumers before live mode.
2. **The maintenance Worker first.** Paste the current `infra/cloudflare/maintenance-worker.js` into
   the Cloudflare dashboard and deploy it: its `BYPASS_PREFIXES` must include `/api/billing/webhook`
   *before* any webhook exists, or the first maintenance window silently eats payment events.
3. **Customer Portal** (Dashboard → Settings → Billing → Customer portal): cancellation **at end of
   period**; plan switching **off**; payment-method update and invoice history **on**.
4. **Retries and emails** (Settings → Billing → Subscriptions and emails): Smart Retries on;
   *if all retries for a payment fail* → **cancel the subscription**; customer emails for
   successful and failed payments on. The code bounds past-due access at 21 days regardless, but
   leaving the subscription past due forever keeps billing someone who has no access.
5. **Webhook endpoint** (Developers → Webhooks → Add endpoint): URL
   `https://gemlab.app/api/billing/webhook`, events `checkout.session.completed`,
   `checkout.session.expired`, `customer.subscription.created`, `customer.subscription.updated`,
   `customer.subscription.deleted`. Copy its signing secret (`whsec_…`) into
   `ZGRADER_STRIPE_WEBHOOK_SECRET` — not the API key.
6. **Keys.** Set `ZGRADER_STRIPE_SECRET_KEY` in the Portainer stack env, redeploy, and check
   `/pricing` shows **Subscribe**. A `sk_test_` key in production logs a warning at every boot.
7. **Prove delivery.** From the Dashboard, send a test event to the endpoint; it must answer 200 and
   a row must appear in `stripe_events`:
   `docker exec zgrader-app-postgres-1 psql -U zgrader -c "SELECT event_id, type FROM stripe_events ORDER BY processed_at DESC LIMIT 5"`.
8. **Prove the bypass (L2).** Attach the maintenance route, then:
   `curl -s -o /dev/null -w "%{http_code}\n" -X POST https://gemlab.app/api/billing/webhook` must print
   **400** (the origin refusing an unsigned request), while
   `curl -s -o /dev/null -w "%{http_code}\n" https://gemlab.app/` prints **503**. Detach the route.

After an outage, press **Reconcile billing** in the admin panel (`POST /admin/billing/reconcile`)
rather than waiting for the worker's daily pass; a redeploy also triggers one at worker boot.
Refunds and disputes are handled in the Stripe Dashboard; a refund does not cancel a subscription
by itself, so cancel it there too — the mirror follows either way.
```

- [ ] **Step 4: The backlog (local only)**

In `docs/superpowers/plans/2026-09-06-remediation-backlog.md`, mark L2 and L3 `[x]` with the PR number once merged, and rewrite "Where we left off" to say what is merged, what is deployed, and which go-live steps (above) are still open. Do **not** `git add` this file — it is gitignored on purpose.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md docs/deployment.md
git commit -m "Document the billing invariants and the go-live checklist"
```

---

### Task 15: Stripe test mode, end to end — then the PR

**Files:** none changed unless a step finds a defect (then: fix under TDD in the owning task's files, and re-run that task's tests).

**Interfaces:** consumes the whole feature. Needs a Stripe account in **test mode** (a sandbox can be used before the business is fully onboarded) and the Stripe CLI.

This is where the spec's unverified assumptions are proved: that the raw body survives the Next.js rewrite, that the Portal can cancel a subscription with an inline price, and that `current_period_start` is the failed renewal's date.

- [ ] **Step 1: Local stack on test keys**

Backend (Git Bash, `backend/`) with `ZGRADER_DATABASE_URL=…/zgrader_test`, `ZGRADER_STRIPE_SECRET_KEY=sk_test_…` from the Dashboard, and the worker running the same way (`./.venv/Scripts/python.exe -m zgrader.worker.main`) with the same env. Frontend via `preview_start`. Then:

```bash
stripe listen --forward-to localhost:3000/api/billing/webhook
```

Put the `whsec_…` it prints into `ZGRADER_STRIPE_WEBHOOK_SECRET` and restart backend and worker. Forwarding to the **frontend port** is the point: a signature that survives this trip has survived the Next.js rewrite.

- [ ] **Step 2: Subscribe**

Signed in and verified, subscribe to monthly with card `4242 4242 4242 4242`. Expect: back on `/account`, "Confirming…" then the card showing the plan and "Renews on …"; `stripe listen` shows 200s; `stripe_events` has rows; `subscriptions` has one `active` row with `amount_pence` equal to the catalog price and `terms_version = 2026-09`.

- [ ] **Step 3: Portal cancel and reactivate**

Manage billing → cancel. Expect "Ends on …" and `cancel_at` set. Reactivate in the Portal → the line returns to "Renews on …" and `cancel_at` is NULL. (This proves the Portal handles inline-priced subscriptions.)

- [ ] **Step 4: Founder seat and the race**

Set `founder_seats` in the admin panel to *(founders so far + 1)*. In two browsers signed in as different verified users, open the annual dialog in both and press Continue within a second of each other. Exactly one Stripe page shows the founder price; the other shows the full annual price. Complete the founder one; `/pricing` then hides the founder line (0 left).

- [ ] **Step 5: Failed renewal with a test clock**

Create a test clock in the Dashboard (Billing → Test clocks) and a customer on it; set that customer's id as a fresh test user's `stripe_customer_id` in `zgrader_test`, then subscribe that user with `4000 0000 0000 0341` (attaches, but every charge fails — the first checkout charge uses a fresh card, so pay the first period with 4242 and switch the default card to 0341 in the Portal). Advance the clock past the renewal. Expect: status `past_due`; `current_period_start` equals the renewal date (the grace anchor's assumption); the account card shows the failed-payment warning; access continues. Advance 22 more days → `/submissions/quota` reports `free`.

- [ ] **Step 6: Account deletion with a live subscription**

Delete an account that holds an active subscription. Expect 204; in the Dashboard the customer is deleted and its subscription canceled; `stripe listen` delivers `customer.subscription.deleted` and it is answered 200.

- [ ] **Step 7: Reconcile after a missed webhook**

Stop `stripe listen`. Cancel a live subscription immediately in the Dashboard. Restart the worker. Expect its boot log `billing reconcile: checked N, corrected 1`, the row `canceled`, and a `billing_reconciled` entry in the admin audit log. Repeat with the admin **Reconcile** button instead of a restart.

- [ ] **Step 8: Full verification, then the PR**

```bash
cd backend && ./.venv/Scripts/python.exe -m pytest -q > /tmp/full.txt 2>&1; echo $?
cd ../frontend && npx tsc --noEmit && npx next build
```

Both clean, `test_backup_script.py` not skipped. Then open the PR with `gh pr create` from this branch against `main`: summary of what ships (billing **off** until the keys are set), the go-live checklist link, screenshots from Tasks 11–12, the Task 15 results, and the six divergences listed at the top of this plan. Wait for Cedric to say "merge it"; he deploys via Portainer, and the go-live steps in `docs/deployment.md` follow separately.

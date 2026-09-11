# Stripe subscriptions — design

**Date:** 2026-09-11
**Status:** draft for review — no code until this is approved and turned into a plan
**Covers:** remediation items L2 (the maintenance Worker would block Stripe's webhook) and L3 (Stripe
integration prerequisites)

---

## 1. Scope

**In v1**

- The monthly and annual plans, sold through Stripe's hosted **Checkout**.
- Stripe's hosted **Customer Portal** for cancelling, changing the card and viewing invoices.
- **Founder pricing** on the yearly plan, as `/pricing` already promises.
- A signature-verified **webhook**, a **reconciliation** sweep behind it, and the maintenance-Worker bypass
  that lets the webhook through.
- Account deletion that cancels billing.
- The copy and legal pages that currently say nothing is sold through the site.

**Not in v1, and why**

| Left out | Why |
|---|---|
| Credit pack | "25 checks, use over a year" is a persistent balance. `plan_entitlements` only expresses *N per rolling window* — the same gap as AGENTS.md's "lifetime allowance". It needs its own data model. Stays arranged by hand. |
| In-hand (physical) pre-grades | An order-and-fulfilment flow (shipping, receipt, turnaround), not a subscription. Its own spec. Stays arranged by hand. |
| Self-serve plan switching | The Portal can only switch between prices defined in Stripe, and this design keeps prices in our database (§3). Monthly → annual is *cancel, then subscribe*. This also removes the mid-period proration question entirely. |
| Disputes / chargebacks | Stripe emails the account owner; the operator handles them in the Dashboard. |
| Stripe Tax | Off. Gibraltar has no VAT, but selling digital services to UK/EU consumers may create obligations — an adviser question (§13). The Checkout builder takes one flag so it can be switched on without redesign. |
| Currencies other than GBP | Everything is priced in pence sterling already. |
| Stripe's Accounts v2 customer API | Public preview outside Connect. We use the established `Customer` object, which `users.stripe_customer_id` already assumes. |

## 2. Decisions made during brainstorming

| Question | Decision |
|---|---|
| What does v1 sell through the site? | Subscriptions only (monthly + annual). |
| Stripe account | None yet; will be a Gibraltar-registered business. Gibraltar is a fully supported Stripe country. GBP only, test mode first. |
| Founder pricing | In v1. |
| Architecture | **Approach 1**: local mirror written from webhooks, prices built inline at checkout from our own rows. Rejected: Stripe `Price` objects synced from the admin panel (two sources of truth for every price, and it reintroduces mid-period plan changes); live Stripe lookups on every entitlement check (a Stripe or network outage would block submissions). |
| Is a founder seat returned when a founder cancels? | **No.** "The first N annual subscribers" means exactly that; leaving forfeits the price, which "locked for as long as they stay" already says. |
| Is `past_due` entitled? | **Yes, bounded** — see §6.5. Losing access on the first failed renewal attempt, while Stripe is still retrying, would punish an expired card as if it were non-payment. |

## 3. Principles this design establishes

These become AGENTS.md invariants when the work lands.

1. **Stripe is the authority on whether someone has paid; `subscriptions` is a mirror of it.** One function
   — `billing.apply_subscription` — writes that mirror. The webhook, the reconcile sweep and the admin
   reconcile button all call it, so there is one place the rules live.
2. **A price lives only in our database.** Checkout builds each line item inline (`price_data`) from
   `plan_entitlements.price_pence` or `Settings.founder_price_pence`. Stripe `Product`s exist (one per plan,
   carrying a name and no amount) but no Stripe `Price` is ever authored by hand.
3. **The client names a plan, never an amount.** The checkout request schema forbids extra fields, so a
   client-supplied price is a 422, not something that is quietly ignored.
4. **Access is never granted because the browser reached the success page.** Only a verified webhook or a
   reconcile pass changes entitlement. The success page reads our database and waits.
5. **The webhook path is never gated by the maintenance Worker.** `/api/billing/webhook` is in
   `BYPASS_PREFIXES`, and a test ties the two strings together.
6. **The webhook is the fast path; reconciliation is the guarantee.** When the whole stack is down,
   Stripe retries for days and then stops. The bypass cannot help with that; a sweep that compares us with
   Stripe can.
7. **A quota window belongs to the plan it was counted under.** When the plan changes, by *any* route, the
   window starts fresh. This is derived from state (§6.5), not performed by each mutation path — the same
   reasoning as the link-preview image's fingerprint, so a path added later cannot forget.

## 4. Components

| Where | What |
|---|---|
| `backend/zgrader/billing.py` | Domain logic, no FastAPI: `create_checkout`, `apply_subscription`, `reconcile`, founder-seat counting, `delete_customer`. |
| `backend/zgrader/billing_stripe.py` | The **only** module that imports `stripe`. A thin adapter: create customer / product / checkout session / portal session, retrieve subscription, list subscriptions, delete customer, cancel+refund a subscription, verify a webhook signature. Configures the pinned API version, a 20-second timeout and two network retries. Tests replace this module; nothing else needs mocking. |
| `backend/zgrader/api/routers/billing.py` | `POST /billing/checkout`, `POST /billing/portal`, `GET /billing/subscription`, `POST /billing/webhook`. |
| `backend/zgrader/api/routers/admin.py` | `POST /admin/billing/reconcile`; `UserQuotaOut` gains billing fields. |
| `backend/zgrader/worker/main.py` | `_reconcile_billing()` on the same monotonic-timer pattern as `_sweep_retention` — first run at boot, then every 24 hours. |
| `backend/zgrader/entitlements.py` | Entitled statuses, the bounded `past_due` grace, and the plan-change window reset. |
| `backend/zgrader/api/routers/auth.py` | `delete_account` deletes the Stripe customer first. |
| `backend/zgrader/config.py` | `stripe_secret_key`, `stripe_webhook_secret`, `billing_enabled`. |
| `infra/cloudflare/maintenance-worker.js` | `/api/billing/webhook` added to `BYPASS_PREFIXES`; docstring says payment callbacks must never be gated. |
| `frontend/app/pricing/`, `frontend/app/account/page.tsx`, `frontend/lib/api.ts`, `frontend/lib/i18n/{en,es}.ts` | Subscribe flow, account billing card, copy. |

## 5. Data model

One Alembic migration. `tests/test_migrations.py` runs it against the real chain.

**`plan_entitlements`** — add `stripe_product_id String(64) NULL UNIQUE`. It is filled in lazily the first
time a plan is sold, and the create call uses Stripe's idempotency key `product-{plan}`, so two first
checkouts cannot create two products. A Product has a name and no amount, so the price stays single-sourced.

**`subscriptions`** — existing columns kept, plus:

| Column | Type | Why |
|---|---|---|
| `status` | `String(32)`, **was** the `subscription_status` Postgres enum | Stripe has statuses the enum lacks (`unpaid`, `incomplete_expired`, `paused`), and adding enum values in a migration is how `b7f4c2e19a83` took the stack down. `ALTER COLUMN … TYPE varchar(32) USING status::text`, then `DROP TYPE subscription_status`. `_ENTITLED_STATUSES` stays an allow-list, so an unknown status is not entitled. |
| `founder` | `Boolean NOT NULL DEFAULT false` | Seat counting and the account badge. |
| `amount_pence` | `Integer NULL` | What *this* subscriber pays, read from Stripe. Makes the founder lock and any later price change visible per subscriber. |
| `current_period_start` | `DateTime(tz) NULL` | Displayed with `current_period_end`; both are read from the subscription **item**, where Stripe's current API versions put them. |
| `cancel_at` | `DateTime(tz) NULL` | Set when a cancellation is pending. Filled from `cancel_at`, or from `current_period_end` when a classic-billing-mode subscription has `cancel_at_period_end = true` — Stripe signals this differently by billing mode. Lets the page say "ends on 14 October". |
| `checkout_attempt_id` | `UUID NULL`, FK `checkout_attempts.id` `ON DELETE SET NULL` | Links the subscription to the attempt that carried the consent (§6.1). |
| `terms_version`, `consented_at` | `String(20) NULL`, `DateTime(tz) NULL` | Copied from the attempt: which Terms were accepted, and when consent to start immediately was given. Our own proof, beside what was bought. |

A **partial unique index** on `subscriptions(user_id)` where the status is entitled, declared in the model
with `postgresql_where` rather than in raw SQL, so `create_all` builds it in the test database too — the
`ix_users_email_lower` trap in reverse.

**New `checkout_attempts`** — one row per Checkout session we create. It doubles as the founder-seat hold
and the consent record.

| Column | Notes |
|---|---|
| `id` | UUID PK. Put in the session's and the subscription's metadata. |
| `user_id` | FK `users.id` `ON DELETE CASCADE`. |
| `plan`, `amount_pence`, `founder` | Decided by the server when the attempt is created. |
| `terms_version`, `consented_at` | From the confirm step (§6.1). |
| `stripe_session_id` | `String(255) NULL UNIQUE` — filled in after the Stripe call returns. |
| `expires_at` | 31 minutes after creation: Stripe's session minimum is 30, plus a minute of slack so a hold never lapses before its session does. |
| `state` | `open` / `completed` / `expired` / `abandoned` (the Stripe call failed). A plain string, for the same reason as `status`. |

**New `stripe_events`** — `event_id String(255) PK`, `type`, `processed_at`. Written in the same
transaction as the event's effect, so a duplicate delivery hits the key and does nothing, and a failed one
rolls back with its effect and is retried.

**`users`** — `stripe_customer_id` already exists. Add `quota_plan String(64) NULL`: the plan the current
window was counted under. `NULL` reads as `free`, which is true of every existing row.

## 6. Flows

### 6.1 Checkout — `POST /billing/checkout`

Request: `{plan, terms_version, immediate_start_consent}` with `extra="forbid"`. The frontend reaches it
through a confirm dialog on `/pricing` that shows the amount (from the catalog) and asks for acceptance of the
current Terms and consent to start immediately.

Refused before anything reaches Stripe:

| Condition | Response |
|---|---|
| Billing is off | 404 — the feature does not exist on this deployment |
| Email not verified | 403, the same gate as submitting |
| Plan unknown, unpriced, or not billed `month`/`year` | 422 — the pack cannot be bought here in v1 |
| `terms_version != CURRENT_TERMS_VERSION`, or consent not `true` | 422 — the page was stale; the dialog re-reads |
| User already has an entitled subscription | 409 — "manage it from your account" |
| User has an `open`, unexpired attempt | 200 with **that** attempt's session URL — two tabs must not become two subscriptions |

Otherwise:

1. **Ensure a Stripe customer.** If `stripe_customer_id` is NULL, create one with the user's email and
   `metadata.user_id`, using the idempotency key `customer-{user_id}`, and save the id.
2. **Decide the amount and reserve a seat** (§6.2), then insert the `checkout_attempts` row and **commit**.
   The Stripe call happens after the commit, so no row lock is held across a network request.
3. **Create the Checkout session**: `mode=subscription`, the customer, one inline line item
   (`currency=gbp`, the plan's product, `unit_amount`, `recurring.interval`), `expires_at`,
   `client_reference_id=user_id`, and `subscription_data.metadata = {user_id, plan, founder,
   checkout_attempt_id}`. Success URL `/account?billing=success`, cancel URL `/pricing`.
4. On success, store `stripe_session_id` and return `{url}`; the browser redirects. If Stripe fails,
   mark the attempt `abandoned` — which releases any seat — and return 503.

### 6.2 Founder seats

- The offer applies to the plan whose `billing_period` is `year` — found by period, not by the name
  `annual`, so renaming a plan cannot silently disable it.
- The offer is live while `founder_price_pence` and `founder_seats` are both non-NULL.
- **Seats taken** = subscriptions with `founder = true` whose status is not `incomplete` or
  `incomplete_expired` (never paid), **plus** attempts with `founder = true`, `state = open` and
  `expires_at > now`.
- Counting and inserting happen in one transaction that takes `SELECT … FOR UPDATE` on the `Settings`
  singleton. Two checkouts racing for the last seat serialise on that row: one gets the founder price and
  the other gets full price.
- Seats are never returned (§2). A former founder who subscribes again takes a new seat only if one remains,
  and no special case exists for them.
- The lock is Stripe's own behaviour: a subscription keeps the amount it started on. Changing the founder
  price — or any price — affects **new** checkouts only.
- `/catalog/pricing` gains `founder_seats_remaining`: a single aggregate, nothing per user, and
  `test_public_payload_key_allowlist` is unaffected because that allowlist covers the share page, not the
  catalog.

### 6.3 Webhook — `POST /billing/webhook`

Public URL: `https://gemlab.app/api/billing/webhook`. It reaches the backend through Caddy → Next.js's
`/api/:path*` rewrite, like every other API call. That rewrite has no `proxy.ts` in front of it, so the
body-buffering limit in the Next.js docs does not apply; the plan's end-to-end check proves the raw body
survives by forwarding the Stripe CLI to the **frontend** port rather than the backend.

1. An `async` endpoint reads the raw body with `await request.body()` **before any parsing**, and verifies
   `Stripe-Signature` against `stripe_webhook_secret`. A missing or bad signature is **400** and costs the
   caller a rate-limit unit. Valid requests cost nothing, so Stripe can never be throttled — the same
   counts-only-failures rule as login, built on `api/ratelimit.py` rather than a second limiter.
2. The verified event is handled in the threadpool (`run_in_threadpool`), since the database session is
   synchronous.
3. `INSERT INTO stripe_events … ON CONFLICT DO NOTHING`. Already there → 200, nothing else.
4. Dispatch:

   | Event | Effect |
   |---|---|
   | `checkout.session.completed` | Retrieve the subscription from Stripe → `apply_subscription`; mark the attempt `completed`. |
   | `checkout.session.expired` | Mark the attempt `expired` (releasing any seat). |
   | `customer.subscription.created` / `.updated` / `.deleted` | Retrieve the subscription from Stripe → `apply_subscription`. |
   | anything else | Recorded; no effect. |

5. Commit → 200. Any exception rolls back everything, **including the `stripe_events` row**, and returns
   500, so Stripe retries.

Subscription events **never trust the payload**: the handler takes the subscription id and retrieves the
current object. Events may arrive out of order, and re-reading makes order irrelevant. It also means the API
version configured on the Dashboard endpoint barely matters — only ids are read from it. The code pins its own
API version in `billing_stripe.py`.

### 6.4 `apply_subscription` — the one writer

Given a subscription object retrieved from Stripe:

1. **Find the user** from `metadata.user_id`, and require that user's `stripe_customer_id` to equal the
   subscription's `customer`. On a mismatch, or no such user (an account deleted since), log at `info` and
   return without change. A mismatch is logged at `warning`: it should never happen.
2. **Duplicate guard — before any write.** If this subscription is entitled, and the user already has a
   *different* entitled subscription, keep the older one. Cancel this newer one in Stripe immediately with a
   full refund of its first invoice, write it below with the status Stripe returns (`canceled`), and audit
   it as `subscription_duplicate_refunded`.
   - The check has to come first. The partial unique index would otherwise reject the write, and the event
     would fail with a 500 that Stripe retries for days.
   - The open-attempt rule in §6.1 makes this a residual race, not a normal path.
3. **Upsert** the `subscriptions` row by `stripe_subscription_id`:
   - `plan`, `founder` and `checkout_attempt_id` come from metadata, which only our server sets.
   - `status` comes from Stripe.
   - `amount_pence` and the period dates come from the first item.
   - `cancel_at` follows the rule in §5.
   - `terms_version` and `consented_at` are copied from the attempt.
4. **Audit** any change of status, plan or founder flag (§6.9).

It never touches quota: §6.5 derives that.

### 6.5 Entitlement and quota

- **Entitled statuses:** `active`, `trialing`, and **`past_due` while `now < current_period_start + 21
  days`**.
  - Anchored on the period's **start**, deliberately. When a renewal fails, Stripe has already advanced the
    subscription into the new period, and the unpaid invoice belongs to it. So `current_period_start` is the
    moment of the failed renewal, while `current_period_end` is a month — or a year — further on. Anchoring
    on the end would grant roughly 51 days of unpaid access on monthly and over a year on annual. §12
    proves the anchor with a Stripe test clock rather than trusting this paragraph.
  - The bound is in code on purpose. Stripe's retry schedule and its "what happens when retries run out"
    setting are Dashboard options.
  - If the setting were ever left at "leave the subscription past due", an unbounded rule would grant
    access forever.
  - The go-live checklist still sets it to cancel (§8), so normally the status turns `canceled` first and
    the bound never bites.
- **Window reset on plan change.** `get_quota` compares `active_plan(user)` with `user.quota_plan`. If they
  differ, it sets `quota_used = 0`, `quota_period_started_at = NULL` and `quota_plan = <active plan>`, the
  same way it already rolls a lapsed window forward on read.
  - That covers every route by which the plan changes: a webhook, reconcile, the `past_due` grace expiring
    with nobody writing anything, or an operator editing a subscription.
  - `_roll_period_forward` never sees one window counted under two plans, which is the question L3 asked.
- Resetting the free counter by subscribing costs money, so it is not a loophole.
- An unlimited plan still records `quota_plan`, so dropping back to free starts a clean window. That is what
  `consume_submission`'s docstring already intends.

### 6.6 Cancellation and the Portal

`POST /billing/portal` returns a Portal session URL for the user's customer (409 if they have none), with the
return URL `/account`.

The Portal is configured in the Stripe Dashboard, listed in `docs/deployment.md`:

- cancellation at **end of period**
- plan switching **off**
- payment-method update and invoice history **on**

Stripe's docs require a product catalogue only for upgrade, downgrade and quantity changes. The plan
therefore includes a test-mode step proving that a Portal cancellation works on a subscription with an inline
price — the docs imply it rather than state it.

Customer journey:

| Action | What happens |
|---|---|
| Cancel | `subscription.updated` with a pending cancellation → `cancel_at` set; access continues. |
| Reactivate | `cancel_at` cleared. |
| End of period | `subscription.deleted` → `canceled` → free, with a fresh window (§6.5). |

Refunds are the operator's, in the Stripe Dashboard. A refund does not cancel a subscription by itself, so the
operator cancels there too, and the webhook or reconcile brings our row into line either way.

### 6.7 Account deletion

- **Stripe first.** If the user has a `stripe_customer_id`, `delete_account` deletes the Stripe customer
  **before** touching our rows. Deleting a customer cancels its subscriptions immediately.
- **If Stripe fails, nothing is deleted.** The endpoint answers 503: "we couldn't cancel your subscription;
  nothing has been deleted — try again". Of the two orders that can half-fail, this is the only safe one.
  The other leaves a card being charged with no account behind it.
- The `customer.subscription.deleted` event that follows finds no user, is recorded, and gets a 200.
  (`customer.deleted` is not among the subscribed events.)
- There is no automatic refund when an account closes mid-period; the Refund Policy says so (§10).
- An account with no Stripe customer is deleted exactly as today, with no Stripe call.
- There is no email-change flow today. If one is added, it must update the Stripe customer's email too, or
  receipts go to the old address.

### 6.8 Reconciliation

`billing.reconcile(db)`:

1. Pages through **every** subscription in the Stripe account (`status=all`) and applies each one. Any
   status, amount or date drift is corrected through the normal writer.
2. Re-retrieves individually every local entitled row that Stripe did not return, and applies what comes
   back. A deleted subscription reads as `canceled`.
3. Marks `open` attempts past `expires_at` as `expired`.

It runs:

- In the **worker**: at boot, which means every redeploy after an outage catches up without being asked, and
  then every 24 hours. It sits on the same monotonic-timer pattern as `_sweep_retention`. It catches and logs
  its own exceptions: it shares a loop with scan analysis, and a Stripe outage must not stop or crash
  analysis. The adapter's timeout bounds how long one call can stall that loop.
- From **`POST /admin/billing/reconcile`**: operator-only, tightly rate-limited. It returns
  `{checked, corrected}`.

Every correction writes a `billing_reconciled` audit entry and logs a warning. A webhook that has been
failing therefore surfaces as drift in the audit log, instead of as silence. Stripe also emails the account
owner when an endpoint keeps failing.

When billing is off, reconcile is a no-op.

### 6.9 Audit

Actions:

- `subscription_started`
- `subscription_changed` (status, plan, founder or `cancel_at`)
- `subscription_ended`
- `subscription_duplicate_refunded`
- `billing_reconciled`

`detail` holds our user id, the plan, the before/after status, the founder flag and Stripe ids — **never an
email address**. `delete_account` scrubs addresses from audit rows by key name (`email`, `target_email`), so
an address under any new key would survive an erasure. A test asserts that no billing audit detail contains
`@`.

## 7. API surface

| Route | Auth | Limiter | Notes |
|---|---|---|---|
| `POST /billing/checkout` | signed in | `user_rate_limit`, tight | §6.1 |
| `POST /billing/portal` | signed in | `user_rate_limit`, moderate | 409 with no customer |
| `GET /billing/subscription` | signed in | `rate_limit`, generous | The user's current subscription (plan, status, amount, founder, period dates, `cancel_at`) or `null`. Polled by `/account?billing=success`. |
| `POST /billing/webhook` | Stripe signature | failures only | §6.3 |
| `POST /admin/billing/reconcile` | operator | admin write limit | §6.8 |
| `GET /admin/users/quota` | operator | unchanged | `UserQuotaOut` gains `subscription_status`, `founder`, `cancel_at` — the lookup the operator uses to apply the 20% in-hand subscriber discount by hand. |
| `GET /catalog/pricing` | public | unchanged | Gains `founder_seats_remaining` and `billing_enabled`. |

`test_rate_limit_coverage.py` passes with no new entries in `UNLIMITED_BY_DESIGN`.

## 8. Configuration and deployment

**Environment:** `ZGRADER_STRIPE_SECRET_KEY` and `ZGRADER_STRIPE_WEBHOOK_SECRET`, both in
`docker-compose.yml`'s backend **and** worker `environment:` blocks, since reconcile runs in the worker.
`test_compose_env_coverage.py` enforces this.

- `billing_enabled` is true only when both are set, like `google_enabled`. With billing off:
  - checkout, portal and webhook answer 404
  - reconcile does nothing
  - `/pricing` keeps "Get in touch"

  So this can merge and deploy before a Stripe account exists.
- In production, an `sk_test_` key **logs a warning** rather than refusing to boot, so a trial run is
  possible.

**Dependencies:** `stripe` goes in `pyproject.toml`; regenerate `requirements.lock` with
`--python-platform linux` (AGENTS.md). `test_lockfile_covers_dependencies.py` catches a missed lock.

**Maintenance Worker:** `/api/billing/webhook` goes in `BYPASS_PREFIXES`, and the docstring gains a sentence:
payment callbacks must never be gated — Stripe retries into a 503 for days and then disables the endpoint,
with nothing in origin logs to explain it. The Worker is pasted into the Cloudflare dashboard by hand, so it is
redeployed there as a deployment step, and **before** the keys are set.

**Go-live checklist** — new section in `docs/deployment.md`, in this order:

1. The Stripe account is onboarded as a Gibraltar business.
2. The maintenance Worker is redeployed with the bypass.
3. The Portal is configured (§6.6).
4. Billing settings: Smart Retries on; **"if all retries fail: cancel the subscription"**; customer emails
   for successful payments and failed payments on.
5. The webhook endpoint is registered with the five event types in §6.3, and its signing secret is copied to
   `ZGRADER_STRIPE_WEBHOOK_SECRET`.
6. The keys are set and the stack redeployed. `/pricing` now shows Subscribe.
7. The Stripe CLI sends one test event to the live endpoint, and `stripe_events` shows it.
8. With the maintenance route attached, the webhook still reaches the origin while `/` returns 503 —
   L2's own verification.

All of this runs in **test mode** first, end to end, before the live keys go in.

## 9. Frontend

**`/pricing`**

- When `billing_enabled`, monthly and annual show **Subscribe** for a signed-in, verified user.
- A signed-out user goes to sign-in first, then back to the plan.
- The pack and in-hand keep "Get in touch".
- The "arranged directly" note shows only while billing is off.
- The founder line gains "{remaining} of {seats} left", and disappears at zero.

**Confirm dialog**

- Shows the plan, the amount and the billing period, read from the catalog.
- Two required checkboxes: acceptance of the Terms (linked), and consent to start immediately with the
  cooling-off wording (§13).
- Continue calls `/billing/checkout` and redirects.

**`/account` billing card**

- No subscription: a link to `/pricing`.
- Subscribed: the plan, the amount, a founder badge, "renews on" or "ends on", and **Manage billing**.
- `past_due`: a warning that the last payment failed, with the same button.
- `?billing=success`: "Confirming your subscription…", polling `/billing/subscription` every 2 seconds for
  up to 30. After that: "This is taking longer than usual — it will appear here shortly; you don't need to pay
  again."

**Admin customer lookup:** status, founder and `cancel_at` columns.

**House rules:** every figure comes from the catalog, never the copy. Both languages. The no-horizontal-scroll
and 24px-target rules apply at 320 / 375 / 768 / 1024 / 1280, signed in and out.

**CSP:** unchanged. Checkout and the Portal are top-level redirects to Stripe-hosted pages, and no Stripe.js
is loaded, so `script-src`, `connect-src` and `form-action 'self'` all stand.

## 10. Copy and legal pages

These change **in the same PR**, in English and Spanish: a published promise and the software change
together.

| Page | Change |
|---|---|
| `/pricing` | As §9. The subtitle's "nothing hidden until checkout" becomes literally true. |
| Terms | "Nothing is sold through this website" → subscriptions are bought on the site and paid through Stripe; the credit pack and in-hand services are arranged directly. |
| Refund Policy | §1's "there is no checkout" corrected. New subscriptions section: cancel any time from the account page; access continues to the end of the period already paid for; no partial refund for the period in progress; closing the account mid-period cancels billing without a refund; the cooling-off position (§13). |
| Privacy — what we collect | Adds the Stripe customer and subscription ids, the plan, the amount paid, and the Terms version and consent time recorded at purchase. |
| Privacy §6 | Closing an account cancels the subscription and deletes the Stripe customer; Stripe retains its own transaction records where the law requires, under Stripe's privacy policy. |
| Privacy §7 | Stripe becomes the fourth named supplier: it processes the payment and sees name, email, card details, billing address and IP. The card number never reaches this service. |
| All three | "Last updated" dates. `CURRENT_TERMS_VERSION` bumped. |

Existing free users are not forced to re-accept anything. Buying is the moment the current Terms are
accepted, and the checkout endpoint refuses a stale version.

**AGENTS.md:** the "Nothing takes payment" known-open entry leaves, and §3's principles are added as
invariants.

## 11. Security properties, restated

- No card data reaches the server (SAQ A); `models/subscription.py` already commits to this.
- Signature checked against the raw body before any parsing.
- Idempotent on event id; order-independent by re-reading.
- No client-supplied amount, price or plan is trusted beyond the plan's *name*.
- The metadata user is cross-checked against the Stripe customer before any write.
- Webhook failures are rate-limited; valid deliveries never are.
- The webhook is exempt from the maintenance Worker, and a test holds the two ends together.
- Emails are kept out of audit detail.

## 12. Testing

**Backend** (pytest on `zgrader_test`; every assertion mutation-checked — revert the fix, watch it fail):

- **Signature**
  - A bad signature → 400, and nothing written.
  - A payload that is **parsed and re-serialised** before verification → 400, proving the check runs on raw
    bytes.
  - Webhook tests sign payloads with a test secret using Stripe's real scheme, so verification is exercised
    rather than mocked.
- **Idempotency and order**
  - The same event twice → one change.
  - `.updated` (canceled) delivered before `.created` (active) → the final state matches what Stripe
    returns.
- **Trust boundaries**
  - Metadata user ≠ customer owner → no change.
  - An `amount` field in the checkout body → 422.
- **Founder seats**
  - The last seat raced from **two database sessions** (the pattern of `test_submission_delete_cascade.py`)
    → exactly one founder attempt.
  - A cancelled founder does not free a seat.
  - An expired or abandoned attempt does.
- **Entitlement**
  - `past_due` is entitled inside the grace period and not after it, with no write in between.
  - `unpaid` and `canceled` are not entitled.
- **Quota**
  - The window resets on free → paid and on paid → free.
  - It also resets when the grace period expires with no write, which proves the reset is derived rather
    than performed.
- **Duplicates:** a second entitled subscription → the newer one is cancelled and refunded, and no 500.
- **Account deletion**
  - Stripe failure → 503, and the user still exists.
  - Success → the Stripe call happens before the commit.
- **Reconcile**
  - Drift is corrected and audited.
  - A locally-live subscription missing from Stripe → `canceled`.
  - Expired attempts are closed.
- **Audit:** no billing audit detail contains `@`.
- **Webhook limiter**
  - A burst of valid events is never 429.
  - Repeated bad signatures are.
- **Billing off:** every billing route is 404, and reconcile is a no-op.
- **Cross-file:** the paths in `maintenance-worker.js`'s `BYPASS_PREFIXES` cover `"/api"` + the webhook
  route's real path.
- **Existing guards:** migrations, compose env coverage, the lockfile and rate-limit coverage all cover the new
  pieces with no exclusions added.

**Frontend:**

- `npx tsc --noEmit` (Spanish completeness) and `npx next build`.
- Browser checks, in both languages and at the five widths:
  - `/pricing` with billing on and off
  - the confirm dialog
  - the account card in each state: none, active, cancelling, past due, founder, confirming

**Stripe test mode, end to end:**

- `stripe listen --forward-to localhost:3000/api/billing/webhook`, through the **frontend**.
- Subscribe with `4242…`.
- Cancel and reactivate in the Portal.
- Force `past_due` with a card that fails on renewal, advancing a Stripe **test clock** to the renewal
  date. Confirm that `current_period_start` is the failed renewal's date, which is what §6.5's grace anchor
  assumes.
- Delete an account that has a live subscription.
- Race two founder checkouts for the last seat.
- Stop the listener, cancel a subscription in the Dashboard, restart the worker → reconcile corrects it.

## 13. External inputs required before go-live

These are not design gaps: the design accommodates any answer. But billing must not be switched on in live
mode until each one is settled.

1. **Cooling-off wording.** For a subscription that gives immediate access to a digital service, consumer
   law generally requires the customer's express request to start within the cancellation period, and an
   acknowledgement of what that does to their right to cancel. The confirm dialog and the Refund Policy carry
   a draft, clearly marked as one, for your adviser to correct.
2. **VAT on sales to UK and EU consumers** from a Gibraltar business. It decides whether Stripe Tax gets
   switched on.
3. **Stripe onboarding** as a Gibraltar entity: registered company, local address, Gibraltar bank account.

## 14. How this closes L2 and L3

| Item | Where |
|---|---|
| L2 — the webhook is blocked by the maintenance Worker | §8 bypass in the same PR, with the cross-file test in §12. §3 principle 6 and §6.8 cover the case the bypass cannot: the stack itself being down. |
| L3 — verify the signature against the raw body | §6.3 step 1; the re-serialised-payload test |
| L3 — idempotent on event id | `stripe_events`, in the same transaction as the effect |
| L3 — never trust a client amount, price or plan | §3 principle 3, §6.1, `extra="forbid"` |
| L3 — mid-period plan changes vs `quota_used` and `quota_period_started_at` | No self-serve switching (§1), and the derived window reset (§6.5) |
| L3 — card data off the server | Hosted Checkout and Portal; no Stripe.js; SAQ A |
| L3 verification — replay twice → one change; bad signature → rejected | §12 |

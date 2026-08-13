"""Published prices come from the database, and follow when it changes.

The point of moving prices out of the site copy is that the operator retunes
them from the admin panel without a deploy -- the same argument
`plan_entitlements.submission_limit` already makes for quota caps.

It also closes a divergence that was live until today: the copy said "the first
check is free" while the seeded free plan granted three a week. Two descriptions
of the same product, in two places, with nothing keeping them honest. The tests
below pin the property that prevents it coming back -- what the shopfront quotes
is read from the row that defines it.
"""

import pytest
from fastapi.testclient import TestClient

from zgrader.api.main import app
from zgrader.auth.security import hash_password
from zgrader.models import PhysicalPriceTier, PlanEntitlement, User, UserRole
from zgrader.models.settings import get_or_create_settings
from zgrader.seed import seed_all

client = TestClient(app)


@pytest.fixture
def seeded(db_session):
    seed_all(db_session)
    return db_session


def _operator_token(db_session, email: str = "pricingop@example.com") -> str:
    db_session.add(
        User(
            email=email,
            hashed_password=hash_password("hunter2pass"),
            role=UserRole.operator,
            is_verified=True,
        )
    )
    db_session.commit()
    return client.post(
        "/auth/login", data={"username": email, "password": "hunter2pass"}
    ).json()["access_token"]


def test_pricing_is_public(seeded):
    """No token. These are the prices on the shopfront, not a credential."""
    assert client.get("/catalog/pricing").status_code == 200


def test_every_seeded_plan_is_published_with_its_allowance(seeded):
    body = client.get("/catalog/pricing").json()
    plans = {p["plan"]: p for p in body["plans"]}

    assert "free" in plans, "the free tier must be quotable"
    free = plans["free"]
    row = seeded.query(PlanEntitlement).filter(PlanEntitlement.plan == "free").one()
    # The whole design in one assertion: the page's number and the enforced
    # number are the same number.
    assert free["submission_limit"] == row.submission_limit
    assert free["period_days"] == row.period_days
    assert free["price_pence"] is None, "the free tier is not sold"


def test_plans_are_ordered_cheapest_first_with_the_free_tier_leading(seeded):
    prices = [p["price_pence"] for p in client.get("/catalog/pricing").json()["plans"]]
    assert prices[0] is None, "unpriced plans sort ahead of paid ones"
    paid = [p for p in prices if p is not None]
    assert paid == sorted(paid)


def test_the_volume_table_is_ordered_and_ends_open(seeded):
    tiers = client.get("/catalog/pricing").json()["physical_tiers"]
    assert [t["min_qty"] for t in tiers] == sorted(t["min_qty"] for t in tiers)
    assert tiers[-1]["max_qty"] is None, "the top band must be open-ended"
    # Per-card price falls as the batch grows; the reverse would be a data
    # entry error worth failing on.
    assert [t["price_pence"] for t in tiers] == sorted(
        (t["price_pence"] for t in tiers), reverse=True
    )


def test_changing_a_price_in_the_panel_changes_the_shopfront(seeded):
    """The reason any of this is in the database."""
    token = _operator_token(seeded)
    headers = {"Authorization": f"Bearer {token}"}

    before = {p["plan"]: p for p in client.get("/catalog/pricing").json()["plans"]}
    assert before["monthly"]["price_pence"] != 777

    resp = client.patch("/admin/plans/monthly", json={"price_pence": 777}, headers=headers)
    assert resp.status_code == 200, resp.text

    after = {p["plan"]: p for p in client.get("/catalog/pricing").json()["plans"]}
    assert after["monthly"]["price_pence"] == 777


def test_changing_a_plan_limit_changes_the_shopfront_too(seeded):
    """Not just the price: the allowance the page advertises is the enforced
    one, so retuning the cap must move the quote with it."""
    token = _operator_token(seeded, "pricingop2@example.com")
    resp = client.patch(
        "/admin/plans/free",
        json={"submission_limit": 9},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text

    plans = {p["plan"]: p for p in client.get("/catalog/pricing").json()["plans"]}
    assert plans["free"]["submission_limit"] == 9


def test_a_volume_band_can_be_retuned(seeded):
    token = _operator_token(seeded, "pricingop3@example.com")
    resp = client.patch(
        "/admin/physical-tiers/10",
        json={"price_pence": 650},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text

    tiers = {t["min_qty"]: t for t in client.get("/catalog/pricing").json()["physical_tiers"]}
    assert tiers[10]["price_pence"] == 650


def test_a_band_cannot_end_before_it_starts(seeded):
    token = _operator_token(seeded, "pricingop4@example.com")
    resp = client.patch(
        "/admin/physical-tiers/10",
        json={"max_qty": 4},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, "a 10-4 band is not a band"


def test_the_loose_figures_are_published_and_editable(seeded):
    token = _operator_token(seeded, "pricingop5@example.com")
    body = client.get("/catalog/pricing").json()
    assert body["founder_seats"] is not None
    assert body["subscriber_discount_pct"] is not None

    resp = client.patch(
        "/admin/settings",
        json={"subscriber_discount_pct": 25},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    assert client.get("/catalog/pricing").json()["subscriber_discount_pct"] == 25


def test_switching_an_offer_off_is_distinct_from_making_it_free(seeded):
    """None means "do not show this", not "costs nothing" -- the page has to be
    able to tell those apart or it will advertise a free founder plan."""
    settings = get_or_create_settings(seeded)
    settings.founder_price_pence = None
    seeded.commit()

    assert client.get("/catalog/pricing").json()["founder_price_pence"] is None


def test_prices_are_whole_pence(seeded):
    """Integers throughout. Money in floats is a rounding bug waiting for a
    total, and a fractional penny on a shopfront is a bug report."""
    body = client.get("/catalog/pricing").json()
    amounts = [p["price_pence"] for p in body["plans"] if p["price_pence"] is not None]
    amounts += [t["price_pence"] for t in body["physical_tiers"]]
    assert all(isinstance(value, int) for value in amounts)


def test_seeding_twice_does_not_duplicate_or_clobber(seeded):
    """Re-seeding happens on every startup, so it must fill gaps only."""
    token = _operator_token(seeded, "pricingop6@example.com")
    client.patch(
        "/admin/plans/monthly",
        json={"price_pence": 1234},
        headers={"Authorization": f"Bearer {token}"},
    )

    seed_all(seeded)

    plans = [p for p in client.get("/catalog/pricing").json()["plans"] if p["plan"] == "monthly"]
    assert len(plans) == 1, "re-seeding duplicated a plan"
    assert plans[0]["price_pence"] == 1234, "re-seeding clobbered a tuned price"
    assert seeded.query(PhysicalPriceTier).count() == 4


def test_the_tier1_placeholder_is_not_advertised(seeded):
    """`tier1` was seeded before there was any pricing -- an unlimited plan
    with a name that was never a product.

    The seeder only adds missing plans, so it cannot remove one; the migration
    retires it instead. This asserts the outcome rather than the mechanism: no
    plan reaches the shopfront under a name a customer would not recognise, and
    in particular not an unlimited one at £0.

    It cannot fail on a fresh test database, which builds from `create_all` and
    never had the row -- the case it guards is the deployed database that did.
    So it is a statement of intent for whoever next edits the seed.
    """
    plans = {p["plan"] for p in client.get("/catalog/pricing").json()["plans"]}
    assert "tier1" not in plans

    unpriced = [
        p
        for p in client.get("/catalog/pricing").json()["plans"]
        if p["price_pence"] is None
    ]
    # Exactly one plan may be free, and it must be the free tier -- anything
    # else with no price renders at £0, which is a claim rather than an
    # omission.
    assert [p["plan"] for p in unpriced] == ["free"]

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

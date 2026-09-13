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


def test_the_sdk_still_speaks_the_api_version_this_code_was_written_for():
    from stripe._api_version import _ApiVersion

    from zgrader import billing_stripe

    assert _ApiVersion.CURRENT == billing_stripe.STRIPE_API_VERSION, (
        "The stripe package now pins a different API version. Re-read "
        "zgrader/billing_stripe.py against that version's changelog before "
        "updating STRIPE_API_VERSION."
    )

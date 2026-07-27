"""Every operator-facing setting must actually reach the container.

Compose only forwards variables named in a service's `environment:` block.
Anything else in `.env` is used for `${...}` substitution inside the compose
file itself and is invisible to the process -- so a setting can exist in
config.py, be documented in .env.example, and still do nothing when set,
with no error to explain why.

That is exactly how ZGRADER_ADMIN_RESET_PASSWORD shipped unreachable: the
code, the docs and the example file all agreed, and the variable never got
past Compose.
"""

from pathlib import Path

from zgrader.config import ZGraderConfig

COMPOSE_FILE = Path(__file__).resolve().parents[2] / "docker-compose.yml"

# Settings deliberately NOT operator-tunable via the environment. Listing them
# explicitly is the point: adding a new setting to config.py forces a
# conscious decision about whether a deployment should be able to set it,
# rather than letting the omission pass silently.
NOT_EXPOSED_IN_COMPOSE = {
    # Fixed container paths, pinned by the volume mounts in docker-compose.yml.
    "scans_dir",
    "reports_dir",
    # Derived from reports_dir by a validator; overriding it independently
    # would put public media somewhere that isn't mounted.
    "public_media_dir",
    # Code-level tuning rather than deployment configuration.
    "ai_timeout_seconds",
    "watcher_debounce_seconds",
    "worker_poll_interval_seconds",
}


def test_every_setting_is_either_exposed_or_explicitly_excluded():
    compose = COMPOSE_FILE.read_text()

    missing = []
    for name in ZGraderConfig.model_fields:
        if name in NOT_EXPOSED_IN_COMPOSE:
            continue
        # Matches how pydantic-settings resolves it: env_prefix + upper name.
        if f"ZGRADER_{name.upper()}" not in compose:
            missing.append(name)

    assert not missing, (
        "these settings are readable from the environment but never passed "
        f"through docker-compose.yml, so setting them does nothing: {sorted(missing)}. "
        "Add them to the `environment: &backend-env` block, or list them in "
        "NOT_EXPOSED_IN_COMPOSE with a reason."
    )


def test_excluded_settings_still_exist():
    """Keeps the allowlist honest as config.py changes."""
    stale = NOT_EXPOSED_IN_COMPOSE - set(ZGraderConfig.model_fields)
    assert not stale, f"NOT_EXPOSED_IN_COMPOSE names settings that no longer exist: {sorted(stale)}"

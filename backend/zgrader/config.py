from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class ZGraderConfig(BaseSettings):
    """Environment-driven infrastructure config.

    Business-level config (branding, auto-publish default) lives in the
    `Settings` DB table instead, since it's editable by the operator at
    runtime without a redeploy.
    """

    model_config = SettingsConfigDict(env_prefix="ZGRADER_", env_file=".env")

    database_url: str = "postgresql+psycopg://zgrader:zgrader@localhost:5432/zgrader"

    scans_dir: Path = Path("/data/scans")
    reports_dir: Path = Path("/data/reports")

    # JWT signing key -- MUST be overridden via ZGRADER_SECRET_KEY in any
    # non-local deployment. The default is 32 bytes (HS256's recommended
    # minimum) purely so local dev doesn't trip PyJWT's short-key warning;
    # it is not a secret.
    secret_key: str = "dev-only-not-a-real-secret-32byte"

    # Fallback DPI used when a scan's image metadata doesn't declare one.
    default_scan_dpi: int = 600

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "noreply@zgrader.local"
    smtp_use_tls: bool = False

    # Debounce window (seconds) the watcher waits after the last filesystem
    # event in a submission folder before treating scans as complete.
    watcher_debounce_seconds: float = 5.0
    # Safety-net poll interval for submissions the watcher may have missed.
    worker_poll_interval_seconds: float = 30.0


config = ZGraderConfig()

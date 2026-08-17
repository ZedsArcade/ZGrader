import logging
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# The value shipped in this file. Production refuses to start on it -- see
# _reject_insecure_production_defaults.
INSECURE_SECRET_KEY = "dev-only-not-a-real-secret-32byte"
_MIN_SECRET_KEY_LENGTH = 32
_INSECURE_DB_CREDENTIALS = "zgrader:zgrader@"


class ZGraderConfig(BaseSettings):
    """Environment-driven infrastructure config.

    Business-level config (branding, auto-publish default) lives in the
    `Settings` DB table instead, since it's editable by the operator at
    runtime without a redeploy.
    """

    model_config = SettingsConfigDict(env_prefix="ZGRADER_", env_file=".env")

    # Guards the checks below and switches off the interactive API docs.
    # Defaults to development so the documented bare-uvicorn workflow and the
    # test suite keep working; docker-compose sets ZGRADER_ENV=production.
    env: Literal["development", "production"] = "development"

    database_url: str = "postgresql+psycopg://zgrader:zgrader@localhost:5432/zgrader"

    # Public origin, used to build the links in verification and password
    # reset emails. Must be the address a customer's browser can reach --
    # behind Cloudflare that's the public hostname, not the container.
    site_url: str = "http://localhost:3000"

    scans_dir: Path = Path("/data/scans")
    reports_dir: Path = Path("/data/reports")

    # Operator-uploaded images served publicly (service tier banners).
    # Defaults to a subdirectory of reports_dir -- see the validator below --
    # so it follows wherever reports actually live rather than pinning a path
    # that would be wrong the moment ZGRADER_REPORTS_DIR is overridden.
    public_media_dir: Path | None = None

    # JWT signing key. The default is publicly visible in this file, so
    # anyone could forge an operator token with it -- production refuses to
    # boot on it rather than trusting the operator to notice.
    secret_key: str = INSECURE_SECRET_KEY

    # Fallback DPI used when a scan's image metadata doesn't declare one.
    default_scan_dpi: int = 600

    # Optional first-operator bootstrap: when both are set, startup seeding
    # creates an operator with these credentials (or promotes an existing
    # client of the same email). Lets an admin account be created via env +
    # redeploy, with no shell command or manual DB editing.
    admin_email: str | None = None
    admin_password: str | None = None

    # Recovery hatch for a locked-out operator. Normally the bootstrap only
    # ever sets the *role* on an account that already exists, so a password
    # changed in the app is never clobbered by a redeploy. Set this to true to
    # also force the password back to ZGRADER_ADMIN_PASSWORD on next start,
    # then unset it -- leaving it on means the environment file is a standing
    # credential for that account.
    admin_reset_password: bool = False

    # Google sign-in. Off unless both are set, so a deployment that hasn't
    # registered an OAuth client simply doesn't offer the button rather than
    # showing one that fails. The redirect URI registered with Google must be
    # <site_url>/api/auth/google/callback -- the browser reaches the backend
    # through the Next.js /api rewrite, so it is the public origin Google
    # sends the user back to, not the container.
    google_client_id: str | None = None
    google_client_secret: str | None = None

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    # Optional external vision-model hook for extra "AI-assisted" analysis
    # observations. Off by default; when disabled the pipeline is unchanged.
    ai_enabled: bool = False
    ai_endpoint: str | None = None
    ai_model: str | None = None
    ai_timeout_seconds: float = 30.0

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "noreply@zgrader.local"
    # STARTTLS: connect in the clear on the submission port (usually 587) and
    # upgrade. This is what most relays want.
    smtp_use_tls: bool = False
    # Implicit TLS ("SMTPS"), where the socket is TLS from the first byte and
    # there is no plaintext phase to upgrade. Port 465 speaks this and *only*
    # this -- pointing smtp_use_tls at 465 cannot work, because there is no
    # readable greeting to send STARTTLS to. The two are alternatives, not
    # layers; see _warn_about_unusable_smtp below, which catches the
    # combination that is always wrong.
    smtp_implicit_tls: bool = False

    # Debounce window (seconds) the watcher waits after the last filesystem
    # event in a submission folder before treating scans as complete.
    watcher_debounce_seconds: float = 5.0
    # Safety-net poll interval for submissions the watcher may have missed.
    worker_poll_interval_seconds: float = 30.0

    # How many analyses may run inside API requests at once.
    #
    # `confirm-crop` runs the whole OpenCV pipeline synchronously in the
    # request. FastAPI runs sync endpoints in the anyio threadpool -- 40 threads
    # by default -- so without a cap forty concurrent submissions become forty
    # concurrent pipelines, and every other sync endpoint queues behind them.
    #
    # This bounds the *API*'s share only. The worker is a separate container
    # and single-threaded, so the box's real ceiling is this + 1.
    max_concurrent_analyses: int = 2

    # Threads OpenCV may use per analysis, applied with cv2.setNumThreads at
    # startup.
    #
    # Left alone, OpenCV uses one thread per core, so `max_concurrent_analyses`
    # would cap the number of analyses while each still fanned out across the
    # whole machine -- a cap that does not mean what it looks like. On an
    # 8-core box, 2 API analyses plus the worker's 1 at 2 threads each is 6
    # threads, which leaves room for Postgres and everything else Unraid runs.
    #
    # Measured on a 4000x3000 photograph, `detect_boundary`: 58.6ms at 24
    # threads, 57.5ms at 4, 64.8ms at 2, 84.7ms at 1. The work stops scaling
    # around 4, so holding it to 2 costs about 11% and 1 costs 45%.
    #
    # Set with the API rather than an environment variable on purpose:
    # `OPENCV_NUM_THREADS` is not an OpenCV variable at all, and the real
    # `OPENCV_FOR_THREADS` is honoured only by some parallel backends -- on a
    # Windows build neither moved getNumThreads(). A knob that silently does
    # nothing is the exact failure test_compose_env_coverage.py exists for.
    #
    # NumPy's bundled OpenBLAS is a separate pool and ignores this; it takes
    # OMP_NUM_THREADS / OPENBLAS_NUM_THREADS, which have to be set before numpy
    # is imported and therefore live in docker-compose.yml rather than here.
    analysis_threads: int = 2

    @model_validator(mode="after")
    def _reject_insecure_production_defaults(self) -> "ZGraderConfig":
        """Refuse to start a production deployment on shipped-default secrets.

        A silent fallback to the key printed in this file means anyone who can
        read the repository can mint a token for any account, including the
        operator. Crashing on boot is the only failure mode that can't be
        missed. In development the same conditions only log a warning.
        """
        problems: list[str] = []
        if self.secret_key == INSECURE_SECRET_KEY:
            problems.append(
                "ZGRADER_SECRET_KEY is still the built-in development value. "
                'Generate one with: python3 -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        elif len(self.secret_key) < _MIN_SECRET_KEY_LENGTH:
            problems.append(
                f"ZGRADER_SECRET_KEY is shorter than {_MIN_SECRET_KEY_LENGTH} characters."
            )
        if _INSECURE_DB_CREDENTIALS in self.database_url:
            problems.append(
                "The database URL still uses the default zgrader/zgrader credentials."
            )

        if problems:
            if self.env == "production":
                raise ValueError(
                    "Refusing to start with insecure defaults (ZGRADER_ENV=production):\n  - "
                    + "\n  - ".join(problems)
                )
            for problem in problems:
                logger.warning("Insecure default in use (fine for development): %s", problem)
        return self

    @model_validator(mode="after")
    def _warn_about_unusable_smtp(self) -> "ZGraderConfig":
        """Say so at boot when mail cannot possibly work.

        Deliberately warns rather than raising, unlike the secrets check above.
        An unreachable relay is a functionality hole, not a security one, and
        refusing to boot would turn a service that still analyses cards into a
        service that is entirely down. The point is that the failure stops
        being *silent*: send_email swallows SMTP errors by design, so a wrong
        relay looks exactly like a working one from the UI, and the symptom
        surfaces days later as a customer who registered and cannot submit.

        Both conditions below are things that cannot work, not things that
        merely look unusual -- a warning nobody can act on trains people to
        ignore the log.
        """
        problems: list[str] = []

        # The shipped default points at the bundled mailhog, which only runs
        # under the `dev` compose profile. In production it resolves to
        # nothing and no mail leaves the server at all.
        if self.env == "production" and self.smtp_host in ("mailhog", "localhost", "127.0.0.1"):
            problems.append(
                f"ZGRADER_SMTP_HOST is {self.smtp_host!r}, which is the development default. "
                "Email confirmation gates card submission, so with no working relay a customer "
                "can register and then find they cannot use the service at all."
            )

        # 465 is implicit TLS only. Connecting in the clear and waiting for a
        # greeting to upgrade will hang and then time out.
        if self.smtp_port == 465 and not self.smtp_implicit_tls:
            problems.append(
                "ZGRADER_SMTP_PORT is 465, which speaks TLS from the first byte, but "
                "ZGRADER_SMTP_IMPLICIT_TLS is false. Set it true, or use port 587 with "
                "ZGRADER_SMTP_USE_TLS=true."
            )

        if self.smtp_implicit_tls and self.smtp_use_tls:
            problems.append(
                "ZGRADER_SMTP_IMPLICIT_TLS and ZGRADER_SMTP_USE_TLS are both true. They are "
                "alternatives, not layers -- implicit TLS wins and STARTTLS is ignored."
            )

        for problem in problems:
            logger.warning("SMTP configuration problem: %s", problem)
        return self

    @model_validator(mode="after")
    def _default_public_media_dir(self) -> "ZGraderConfig":
        """Put public media under the reports volume unless told otherwise.

        The reports volume is already mounted read-write into the backend
        container, so this needs no extra mount; and unlike scans_dir it
        isn't walked by the watcher, so a folder here can't be mistaken for
        a submission. ZGRADER_PUBLIC_MEDIA_DIR overrides it.
        """
        if self.public_media_dir is None:
            self.public_media_dir = self.reports_dir / "public"
        return self


config = ZGraderConfig()

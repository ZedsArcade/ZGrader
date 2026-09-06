"""Per-IP rate limiting for the endpoints worth guessing against.

An in-process fixed-window counter rather than Redis: the deployment is a
single uvicorn worker on one box, so a shared store would buy nothing and
cost a service. If this ever runs multi-worker, this needs replacing -- each
worker would keep its own counters and the effective limit would multiply.

Cloudflare's WAF can rate-limit at the edge too, and should, but the app
must not depend on a control it doesn't own.
"""

import threading
import time
from collections import defaultdict

from fastapi import Depends, HTTPException, Request, status

from zgrader.config import config

# Header Cloudflare sets to the real client address. Trusted only in
# production, where the origin is expected to sit behind the tunnel and be
# unreachable directly -- otherwise a client could set it themselves and get
# a fresh bucket per request.
_CF_HEADER = "cf-connecting-ip"
_XFF_HEADER = "x-forwarded-for"


def client_ip(request: Request) -> str:
    """Best available client address.

    Behind Cloudflare the socket peer is the tunnel, so without this every
    visitor would share one rate-limit bucket and lock each other out.
    """
    if config.env == "production":
        cf = request.headers.get(_CF_HEADER)
        if cf:
            return cf.strip()
        forwarded = request.headers.get(_XFF_HEADER)
        if forwarded:
            # Left-most entry is the original client; the rest are proxies.
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class _FixedWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> int | None:
        """Record a hit. Returns None if allowed, or seconds to wait if not."""
        retry_after = self.peek(key, limit, window_seconds)
        if retry_after is None:
            self.record(key, window_seconds)
        return retry_after

    def peek(self, key: str, limit: int, window_seconds: int) -> int | None:
        """Seconds to wait if the key is already at its limit, else None.

        Unlike check() this records nothing, so a caller can decide after the
        fact whether the request should count against the allowance.
        """
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            hits = [t for t in self._hits[key] if t > cutoff]
            self._hits[key] = hits
            if len(hits) >= limit:
                return max(1, int(hits[0] + window_seconds - now))
        return None

    def record(self, key: str, window_seconds: int) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            hits = [t for t in self._hits[key] if t > cutoff]
            hits.append(now)
            self._hits[key] = hits

    def reset(self) -> None:
        """Test helper -- state is process-global, so it has to be clearable."""
        with self._lock:
            self._hits.clear()


_limiter = _FixedWindowLimiter()
reset = _limiter.reset


def rate_limit(name: str, limit: int, window_seconds: int):
    """FastAPI dependency limiting `limit` requests per `window_seconds` per IP.

    Keyed by route name as well as IP so a login attempt doesn't consume a
    password-reset allowance.
    """

    # Named distinctly from user_rate_limit's inner closure below --
    # tests/test_rate_limit_coverage.py identifies a route's limiter by this
    # function's __name__, so a generic name here (e.g. the idiomatic
    # "dependency") would let it collide with any future FastAPI dependency
    # factory of the same shape and silently stop proving anything.
    def _ip_rate_limit_dependency(request: Request) -> None:
        retry_after = _limiter.check(f"{name}:{client_ip(request)}", limit, window_seconds)
        if retry_after is not None:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many attempts. Please wait and try again.",
                headers={"Retry-After": str(retry_after)},
            )

    return _ip_rate_limit_dependency


def user_rate_limit(name: str, limit: int, window_seconds: int):
    """Like rate_limit, but keyed on the authenticated user rather than the IP.

    For endpoints where the attacker already holds a valid token: IP-keying
    lets them rotate addresses to refill the bucket, and the account is the
    thing being attacked, not the address.
    """
    from zgrader.api.deps import get_current_user
    from zgrader.models import User

    # Named distinctly from rate_limit's inner closure above -- see the
    # comment there. This is the name the coverage test looks for to confirm
    # a route is keyed on the user rather than just "has some limiter".
    def _user_rate_limit_dependency(user: "User" = Depends(get_current_user)) -> None:
        retry_after = _limiter.check(f"{name}:user:{user.id}", limit, window_seconds)
        if retry_after is not None:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many attempts. Please wait and try again.",
                headers={"Retry-After": str(retry_after)},
            )

    return _user_rate_limit_dependency


LOGIN_LIMIT = 5
LOGIN_WINDOW_SECONDS = 900


def _login_key(request: Request) -> str:
    return f"login:{client_ip(request)}"


def login_rate_limit(request: Request) -> None:
    """Throttle login once too many *failed* attempts came from this address.

    Successful logins deliberately don't consume the allowance. Counting them
    would lock out an office, a household, or anyone behind carrier-grade NAT
    who happens to share an address with other legitimate users -- and it
    slows a password guesser down not at all, since a guesser has no
    successful attempts to spend.
    """
    retry_after = _limiter.peek(_login_key(request), LOGIN_LIMIT, LOGIN_WINDOW_SECONDS)
    if retry_after is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many attempts. Please wait and try again.",
            headers={"Retry-After": str(retry_after)},
        )


def note_failed_login(request: Request) -> None:
    """Charge a failed login against the address it came from."""
    _limiter.record(_login_key(request), LOGIN_WINDOW_SECONDS)


# Deliberately tight: these gate outbound email, so every request counts --
# unlike login there's no "success" that should be free.
register_rate_limit = rate_limit("register", limit=5, window_seconds=3600)
password_reset_rate_limit = rate_limit("password_reset", limit=3, window_seconds=3600)
verification_resend_rate_limit = rate_limit("verify_resend", limit=3, window_seconds=3600)

# Looser than the email-sending limits above, because this sends no mail and
# an authenticated person retrying a connect they abandoned at Google's
# account chooser is ordinary rather than suspicious. It exists so minting
# signed link states is not an unbounded operation.
google_link_rate_limit = rate_limit("google_link", limit=10, window_seconds=900)

"""Hand-rolled email+password auth (passlib + PyJWT).

We evaluated fastapi-users first, per the plan, but its SQLAlchemy adapter
(fastapi_users_db_sqlalchemy) requires an async SQLAlchemy session, which
would mean either mixing async and sync DB access across the app or
rewriting the sync analysis pipeline/worker onto an async engine. Neither is
worth it for a single-operator app at this scale, so auth is hand-rolled
here instead -- the fallback the plan explicitly allowed for.
"""

import datetime
import secrets

import jwt
from passlib.context import CryptContext

from zgrader.config import config

_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
VERIFICATION_TOKEN_TTL = datetime.timedelta(hours=24)
PASSWORD_RESET_TOKEN_TTL = datetime.timedelta(hours=1)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# A real bcrypt hash of a value nothing can supply, used to burn the same
# ~250ms when an email doesn't exist as when it does. Without it, login
# short-circuits on the missing user and answers ~1000x faster, which tells
# an attacker which addresses are registered.
_DUMMY_HASH = _pwd_context.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _pwd_context.verify(password, hashed)


def waste_password_comparison() -> None:
    """Spend the cost of a password check without having a user to check."""
    _pwd_context.verify("not-the-password", _DUMMY_HASH)


def create_access_token(user_id: str, token_version: int) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES),
        # Compared against the user's current version on every request, so
        # bumping it server-side invalidates every token already issued --
        # the only revocation available without a session store.
        "ver": token_version,
    }
    return jwt.encode(payload, config.secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> tuple[str, int] | None:
    """Returns (user_id, token_version), or None if the token is unusable."""
    try:
        payload = jwt.decode(token, config.secret_key, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    # Tokens minted before `ver` existed are treated as version 1, matching
    # the column default, so this release doesn't log everyone out.
    return user_id, int(payload.get("ver", 1))


def generate_verification_token() -> str:
    return secrets.token_urlsafe(32)


def generate_password_reset_token() -> str:
    return secrets.token_urlsafe(32)


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)

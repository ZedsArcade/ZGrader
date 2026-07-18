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

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _pwd_context.verify(password, hashed)


def create_access_token(user_id: str) -> str:
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, config.secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, config.secret_key, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")


def generate_verification_token() -> str:
    return secrets.token_urlsafe(32)

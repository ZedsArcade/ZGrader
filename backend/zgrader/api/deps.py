from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from zgrader.auth.security import decode_access_token
from zgrader.db import get_db
from zgrader.models import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


_INVALID_TOKEN = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    "Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    decoded = decode_access_token(token)
    if decoded is None:
        raise _INVALID_TOKEN
    user_id, token_version = decoded
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise _INVALID_TOKEN
    # A password change or reset bumps the stored version, which retires every
    # token issued before it. Same 401 as a bad token: whether an account
    # exists is not something an unauthenticated caller should learn.
    if token_version != user.token_version:
        raise _INVALID_TOKEN
    return user


def require_operator(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.operator:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Operator role required")
    return user


def require_verified_user(user: User = Depends(get_current_user)) -> User:
    """Gate for actions that cost storage or compute.

    Applied here rather than at login on purpose: locking someone out of their
    own account because an email didn't arrive is disproportionate, but letting
    an unverified address consume disk and analysis time isn't reasonable
    either. Signing in and reading existing work stays open.
    """
    if not user.is_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Please confirm your email address first -- check your inbox for the link.",
        )
    return user

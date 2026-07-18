from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from zgrader.api.deps import get_current_user
from zgrader.auth.security import (
    create_access_token,
    generate_verification_token,
    hash_password,
    verify_password,
)
from zgrader.db import get_db
from zgrader.models import User, UserRole
from zgrader.schemas.auth import RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=UserRole.client,
        is_verified=False,
        verification_token=generate_verification_token(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/verify/{token}", response_model=UserOut)
def verify_email(token: str, db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.verification_token == token).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invalid verification token")
    user.is_verified = True
    user.verification_token = None
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> TokenResponse:
    # form_data.username carries the email (OAuth2PasswordRequestForm's field
    # name is fixed to "username" by the spec it implements).
    user = db.query(User).filter(User.email == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user

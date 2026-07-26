import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session

from zgrader.api.deps import get_current_user
from zgrader.api.ratelimit import (
    login_rate_limit,
    note_failed_login,
    password_reset_rate_limit,
    register_rate_limit,
    verification_resend_rate_limit,
)
from zgrader.auth.security import (
    PASSWORD_RESET_TOKEN_TTL,
    VERIFICATION_TOKEN_TTL,
    create_access_token,
    generate_password_reset_token,
    generate_verification_token,
    hash_password,
    utcnow,
    verify_password,
    waste_password_comparison,
)
from zgrader.db import get_db
from zgrader.email.notifications import (
    send_already_registered_email,
    send_password_changed_email,
    send_password_reset_email,
    send_verification_email,
)
from zgrader.models import AuditLog, User, UserRole
from zgrader.models.settings import get_or_create_settings
from zgrader.storage import purge_submission_files
from zgrader.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Bumped whenever the terms change, and recorded against each acceptance so
# you can show which version someone agreed to.
CURRENT_TERMS_VERSION = "2026-07"


def _find_by_email(db: Session, email: str) -> User | None:
    """Case-insensitive lookup.

    Addresses are stored lowercased, but comparing on lower() as well means a
    row written before that normalisation still matches.
    """
    return db.query(User).filter(func.lower(User.email) == email.strip().lower()).first()


def _issue_verification_token(user: User) -> None:
    user.verification_token = generate_verification_token()
    user.verification_token_expires_at = utcnow() + VERIFICATION_TOKEN_TTL


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(register_rate_limit)],
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User | UserOut:
    """Create an account.

    Deliberately returns 201 whether or not the address is already taken: a
    distinct 409 turns this endpoint into a way to test which email addresses
    have accounts here. The person who actually owns the inbox is told, via
    an email pointing them at sign-in, and nobody else learns anything.
    """
    email = payload.email.strip().lower()
    settings = get_or_create_settings(db)
    now = utcnow()

    existing = _find_by_email(db, email)
    if existing is not None:
        send_already_registered_email(existing, settings)
        # A synthesised body, never the real row: returning `existing` would
        # hand the caller that account's id, role and verification state,
        # which is a worse leak than the 409 this replaced. Every field here
        # is what a genuine new registration would have produced.
        return UserOut(
            id=uuid.uuid4(),
            email=email,
            is_verified=False,
            role=UserRole.client,
            display_name=None,
            marketing_consent=payload.marketing_consent,
            terms_accepted_at=now,
        )

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        role=UserRole.client,
        is_verified=False,
        terms_accepted_at=utcnow(),
        terms_version=CURRENT_TERMS_VERSION,
        marketing_consent=payload.marketing_consent,
    )
    _issue_verification_token(user)
    db.add(user)
    db.commit()
    db.refresh(user)

    send_verification_email(user, settings)
    return user


# Declared before /verify/{token}: FastAPI matches routes in definition
# order, so a path parameter would otherwise capture the literal
# "resend" and this endpoint would 404.
@router.post(
    "/verify/resend",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(verification_resend_rate_limit)],
)
def resend_verification(
    payload: ResendVerificationRequest, db: Session = Depends(get_db)
) -> Response:
    """Always 204 -- like the reset flow, this must not reveal which addresses
    exist or which are already verified."""
    user = _find_by_email(db, payload.email)
    if user is not None and not user.is_verified:
        _issue_verification_token(user)
        db.commit()
        send_verification_email(user, get_or_create_settings(db))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/verify/{token}", response_model=UserOut)
def verify_email(token: str, db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.verification_token == token).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invalid verification token")
    expires_at = user.verification_token_expires_at
    if expires_at is not None and expires_at < utcnow():
        raise HTTPException(
            status.HTTP_410_GONE,
            "This confirmation link has expired. Request a new one from the sign-in page.",
        )
    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires_at = None
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(login_rate_limit)])
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    # form_data.username carries the email (OAuth2PasswordRequestForm's field
    # name is fixed to "username" by the spec it implements).
    user = _find_by_email(db, form_data.username)
    if user is None:
        # Spend the same time a real password check costs. Short-circuiting
        # here would answer ~1000x faster for an unknown address, which is a
        # readable signal for whether an account exists.
        waste_password_comparison()
        note_failed_login(request)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not verify_password(form_data.password, user.hashed_password):
        note_failed_login(request)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")

    user.last_login_at = utcnow()
    db.commit()
    return TokenResponse(access_token=create_access_token(str(user.id), user.token_version))


@router.post(
    "/forgot-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(password_reset_rate_limit)],
)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> Response:
    """Always 204, whether or not the address exists."""
    user = _find_by_email(db, payload.email)
    if user is not None:
        user.password_reset_token = generate_password_reset_token()
        user.password_reset_expires_at = utcnow() + PASSWORD_RESET_TOKEN_TTL
        db.commit()
        send_password_reset_email(user, get_or_create_settings(db))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> Response:
    user = db.query(User).filter(User.password_reset_token == payload.token).first()
    expires_at = user.password_reset_expires_at if user else None
    if user is None or expires_at is None or expires_at < utcnow():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "This reset link is invalid or has expired."
        )

    user.hashed_password = hash_password(payload.password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    # Whoever forced the reset may be holding a live token; bumping the
    # version retires every session, which is the point of resetting.
    user.token_version += 1
    # Someone who can reset via email has proved they control the inbox.
    user.is_verified = True
    db.commit()
    send_password_changed_email(user, get_or_create_settings(db))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/change-password", response_model=TokenResponse)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Requires the current password, so a borrowed session can't lock the
    real owner out."""
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")

    user.hashed_password = hash_password(payload.new_password)
    user.token_version += 1
    db.commit()
    db.refresh(user)
    send_password_changed_email(user, get_or_create_settings(db))
    # Every existing token is now stale, including the caller's, so hand back
    # a fresh one rather than signing them out of the tab they're using.
    return TokenResponse(access_token=create_access_token(str(user.id), user.token_version))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/me", response_model=UserOut)
def update_profile(
    payload: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    updates = payload.model_dump(exclude_unset=True)
    if "display_name" in updates:
        name = (updates["display_name"] or "").strip()
        user.display_name = name or None
    if "marketing_consent" in updates:
        user.marketing_consent = bool(updates["marketing_consent"])
    db.commit()
    db.refresh(user)
    return user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    """Close the account and erase the personal data behind it.

    A hard delete, not a soft one: a row flagged `deleted_at` still holds the
    very data an erasure request is about. Audit rows are kept but detached
    from the person -- the record that something happened has value for
    service integrity; the record of *who* does not, once they've left.

    Operators can't delete themselves this way; losing the last operator
    would leave the admin panel unreachable.
    """
    if user.role == UserRole.operator:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Operator accounts can't be deleted from here.",
        )

    codes = [s.submission_code for s in user.submissions]

    # Detach the audit trail before the FK targets disappear. Nulling user_id
    # is the anonymisation: the action and its detail survive, the identity
    # doesn't.
    db.query(AuditLog).filter(AuditLog.user_id == user.id).update(
        {AuditLog.user_id: None}, synchronize_session=False
    )
    for submission in list(user.submissions):
        db.query(AuditLog).filter(AuditLog.submission_id == submission.id).update(
            {AuditLog.submission_id: None}, synchronize_session=False
        )
    db.add(
        AuditLog(
            submission_id=None,
            user_id=None,
            action="account_deleted",
            detail={"submissions_removed": len(codes)},
        )
    )

    db.delete(user)
    db.commit()

    # After the commit, so a filesystem failure can't leave orphaned DB rows
    # pointing at files that are already gone.
    for code in codes:
        purge_submission_files(code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import Text, cast, func
from sqlalchemy.orm import Session

from zgrader.api.deps import get_current_user
from zgrader.auth import google as google_oauth
from zgrader.config import config
from zgrader.api.ratelimit import (
    google_link_rate_limit,
    login_rate_limit,
    note_failed_login,
    password_reset_rate_limit,
    rate_limit,
    register_rate_limit,
    user_rate_limit,
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
from zgrader.models import GOOGLE, AuditLog, Identity, User, UserRole
from zgrader.models.settings import get_or_create_settings
from zgrader.storage import purge_submission_files
from zgrader.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    GoogleLinkStartOut,
    GoogleStatusOut,
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
CURRENT_TERMS_VERSION = "2026-08"

# change-password is user-keyed, not IP-keyed: the attacker worth defending
# against here already holds a valid token and can rotate addresses at will,
# so an IP bucket buys nothing and the account is what's actually under
# attack. Tight, because it's a password oracle -- verify_password against a
# stolen token is exactly the guess a brute-forcer wants to make for free.
_change_password_limit = user_rate_limit("change_password", limit=5, window_seconds=900)

# The rest of this file is IP-keyed, same as login: these redeem a token
# rather than a credential, but a redeemable token is still worth throttling
# guesses against.
_reset_password_redeem_limit = rate_limit("reset_password_redeem", limit=10, window_seconds=3600)
_verify_redeem_limit = rate_limit("verify_redeem", limit=10, window_seconds=3600)
_google_start_limit = rate_limit("google_start", limit=20, window_seconds=900)
_google_callback_limit = rate_limit("google_callback", limit=20, window_seconds=900)

# Ordinary authenticated account actions -- not guessing targets, so
# generous, but not unlimited: a runaway client or a credentialled scraper
# should meet a wall before the box does, same reasoning as submissions.py's
# per-IP ceilings.
_profile_read_limit = rate_limit("profile_read", limit=300, window_seconds=300)
_profile_update_limit = rate_limit("profile_update", limit=30, window_seconds=900)
# Destructive and irreversible, so tighter than an ordinary write.
_account_delete_limit = rate_limit("account_delete", limit=10, window_seconds=3600)
_google_status_limit = rate_limit("google_status", limit=120, window_seconds=60)
_google_unlink_limit = rate_limit("google_unlink", limit=10, window_seconds=900)


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


@router.post(
    "/verify/{token}",
    response_model=UserOut,
    dependencies=[Depends(_verify_redeem_limit)],
)
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
    if user is None or not user.has_usable_password:
        # Spend the same time a real password check costs. Short-circuiting
        # here would answer ~1000x faster for an unknown address, which is a
        # readable signal for whether an account exists.
        #
        # A Google-only account takes this branch too, and gets the identical
        # message: saying "this address signs in with Google" would confirm
        # the address is registered to anyone who guessed it.
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


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_reset_password_redeem_limit)],
)
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


@router.post(
    "/change-password",
    response_model=TokenResponse,
    dependencies=[Depends(_change_password_limit)],
)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Requires the current password, so a borrowed session can't lock the
    real owner out."""
    if not user.has_usable_password:
        # A Google-only account has no current password to prove. Setting one
        # goes through the reset-by-email flow instead, which proves control
        # of the inbox rather than of a password that never existed.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This account signs in with Google. Use 'forgotten password' to set a password.",
        )
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


@router.get("/me", response_model=UserOut, dependencies=[Depends(_profile_read_limit)])
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/me", response_model=UserOut, dependencies=[Depends(_profile_update_limit)])
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


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_account_delete_limit)],
)
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

    # Nulling user_id is *most* of the anonymisation, but two actions record
    # the address in `detail` rather than relying on the FK, so on its own it
    # would leave the very thing an erasure is about sitting in the JSONB body.
    # Scrub those keys first, while user_id still identifies the rows -- after
    # the null below there is nothing left to find them by.
    db.query(AuditLog).filter(AuditLog.user_id == user.id).update(
        {AuditLog.detail: AuditLog.detail.op("-")(cast("email", Text))},
        synchronize_session=False,
    )
    # `user_quota_adjusted` is written by an *operator* acting on this account,
    # so its user_id is the operator's and the subject is named in the body.
    db.query(AuditLog).filter(AuditLog.detail["target_user_id"].astext == str(user.id)).update(
        {AuditLog.detail: AuditLog.detail.op("-")(cast("target_email", Text))},
        synchronize_session=False,
    )

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


@router.get(
    "/google/status",
    response_model=GoogleStatusOut,
    dependencies=[Depends(_google_status_limit)],
)
def google_status() -> GoogleStatusOut:
    """Whether this deployment offers Google sign-in.

    The frontend asks before rendering the button, so an install that hasn't
    registered an OAuth client shows no button rather than one that dead-ends
    on a misconfiguration.
    """
    return GoogleStatusOut(enabled=config.google_enabled)


@router.get("/google/start", dependencies=[Depends(_google_start_limit)])
def google_start(next: str = "/dashboard") -> RedirectResponse:
    """Send the browser to Google's account chooser."""
    if not config.google_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Google sign-in is not configured")
    return RedirectResponse(
        google_oauth.authorization_url(google_oauth.issue_state(next)),
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.post("/google/link/start", response_model=GoogleLinkStartOut)
def google_link_start(
    user: User = Depends(get_current_user), _: None = Depends(google_link_rate_limit)
) -> GoogleLinkStartOut:
    """Begin attaching a Google account to the account already signed in.

    Returns the URL instead of redirecting, and that is the point rather than
    a style choice. The session token lives in localStorage, so it rides on an
    XHR and *not* on a navigation -- had this been a plain link to a redirect,
    the server would have had no idea who was asking. Authenticating here and
    handing back a URL keeps the proof of identity on the request that can
    carry it, and reduces the navigation to a signed state that already names
    the account.
    """
    if not config.google_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Google sign-in is not configured")
    return GoogleLinkStartOut(
        url=google_oauth.link_authorization_url(google_oauth.issue_link_state(str(user.id)))
    )


@router.delete(
    "/google/link",
    response_model=TokenResponse,
    dependencies=[Depends(_google_unlink_limit)],
)
def google_unlink(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TokenResponse:
    """Detach the Google account, provided that leaves a way back in.

    Refused without a password, because an account that only signs in through
    Google and then removes Google has locked itself out permanently. The
    escape route exists and the message names it: forgot-password sets a hash
    on an account that never had one.

    token_version is bumped for the same reason a password change bumps it --
    this removes a credential. If somebody had attached *their* Google account
    to this one, unlinking is the remediation, and without the bump whatever
    session they already hold would outlive the change meant to end it. That
    retires the caller's own token too, so a fresh one is returned, exactly as
    change-password does.
    """
    identity = (
        db.query(Identity)
        .filter(Identity.user_id == user.id, Identity.provider == GOOGLE)
        .first()
    )
    if identity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No Google account is connected.")
    if not user.has_usable_password:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Set a password first, or you would have no way to sign in. "
            "Use the forgotten-password link to choose one.",
        )

    db.delete(identity)
    user.token_version += 1
    # No address in `detail`: delete_account scrubs the keys `email` and
    # `target_email` specifically, so a new key carrying one would slip
    # silently past an erasure request.
    db.add(AuditLog(submission_id=None, user_id=user.id, action="google_unlinked", detail={}))
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(str(user.id), user.token_version))


def _google_failure(message: str) -> RedirectResponse:
    """Hand the browser back to the login page with a readable reason.

    Errors go in the query string rather than the fragment because they carry
    nothing sensitive -- unlike the token on the success path below.
    """
    return RedirectResponse(
        f"{config.site_url.rstrip('/')}/login?{urlencode({'oauth_error': message})}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


def _google_link_callback(code: str, state: str, db: Session) -> RedirectResponse:
    """The callback's other half: attach this Google account to a known user.

    Email is deliberately not compared against the account's own address. The
    person has already proved both sides -- a password session to mint the
    state, and Google to get here -- so a mismatch means a work and a personal
    account, not an impostor. Requiring a match would add a failure mode
    without adding proof, and `users.email` is left alone: it is the address
    we write to, and signing in with Google is not a request to change it.
    """
    base = config.site_url.rstrip("/")

    def failure(message: str) -> RedirectResponse:
        return RedirectResponse(
            f"{base}/account?{urlencode({'google_error': message})}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    try:
        user_id = google_oauth.verify_link_state(state)
        subject, _email = google_oauth.exchange_code_for_profile(code)
    except google_oauth.GoogleAuthError as exc:
        return failure(str(exc))

    user = db.get(User, uuid.UUID(user_id)) if _is_uuid(user_id) else None
    if user is None:
        return failure("That account no longer exists.")

    existing = (
        db.query(Identity)
        .filter(Identity.provider == GOOGLE, Identity.provider_user_id == subject)
        .first()
    )
    if existing is not None:
        if existing.user_id == user.id:
            # Already done. Idempotent rather than an error: a double-submit
            # or a back button should not read as a failure.
            return RedirectResponse(
                f"{base}/account?google_linked=1", status_code=status.HTTP_307_TEMPORARY_REDIRECT
            )
        return failure("That Google account is already connected to a different account.")

    db.add(Identity(user_id=user.id, provider=GOOGLE, provider_user_id=subject))
    # See google_unlink: no address in `detail`.
    db.add(AuditLog(submission_id=None, user_id=user.id, action="google_linked", detail={}))
    db.commit()
    return RedirectResponse(
        f"{base}/account?google_linked=1", status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


@router.get("/google/callback", dependencies=[Depends(_google_callback_limit)])
def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Where Google returns the user.

    Ends in a redirect either way, because the browser is here as a result of
    a navigation -- returning JSON would leave the person looking at raw text.

    On success the session token travels in the URL *fragment*. A fragment is
    never sent to a server, so it stays out of access logs, proxy logs and the
    Referer header, which a query parameter would not.
    """
    if not config.google_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Google sign-in is not configured")
    if error or not code or not state:
        # The user pressed cancel on Google's consent screen, or the callback
        # was reached without a code.
        return _google_failure("Google sign-in was cancelled.")

    # Both flows come back to this one URI, so dispatch on the state's own
    # declared type -- verified, not merely read, so a forged state cannot
    # choose which branch runs.
    if google_oauth.state_type(state) == google_oauth.LINK_STATE_TYPE:
        return _google_link_callback(code, state, db)

    try:
        next_path = google_oauth.verify_state(state)
        subject, email = google_oauth.exchange_code_for_profile(code)
    except google_oauth.GoogleAuthError as exc:
        return _google_failure(str(exc))

    identity = (
        db.query(Identity)
        .filter(Identity.provider == GOOGLE, Identity.provider_user_id == subject)
        .first()
    )

    if identity is not None:
        user = identity.user
    else:
        existing = _find_by_email(db, email)
        if existing is not None:
            # Refused rather than linked. Linking on a matching address is how
            # an account gets taken over: anyone who can obtain a provider
            # account bearing someone else's address inherits their account.
            # Requiring the password proves the two are the same person.
            return _google_failure(
                "An account already exists for that email address. "
                "Sign in with your password instead."
            )
        user = User(
            email=email,
            hashed_password=None,
            # Google states the address is verified (checked during exchange),
            # which is the same proof our own emailed link provides -- so this
            # account skips the verification step rather than being stranded
            # behind an SMTP setup it never needed.
            is_verified=True,
            role=UserRole.client,
        )
        db.add(user)
        db.flush()
        db.add(Identity(user_id=user.id, provider=GOOGLE, provider_user_id=subject))
        db.add(
            AuditLog(
                submission_id=None,
                user_id=user.id,
                action="account_created_via_google",
                detail={"email": email},
            )
        )

    user.last_login_at = utcnow()
    db.commit()

    token = create_access_token(str(user.id), user.token_version)
    base = config.site_url.rstrip("/")
    return RedirectResponse(
        f"{base}/auth/google#{urlencode({'token': token, 'next': next_path})}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
